# This module is licensed by its authors under the GNU Affero General Public
# License 3.0.

"""
This module analyzes Blender scene objects and outputs a dictionary with
information about its relationships and bones in a directed graph.

These functions assume that all scene objects’ data-blocks and pose data are up
to date (by using `update_from_editmode`_). In particular, they assume that
armatures’ Bones and PoseBones are synchronized.

.. _update_from_editmode: https://docs.blender.org/api/latest/bpy.types.Object.html#bpy.types.Object.update_from_editmode
""" # noqa

from .analyzebones import mirror_symbol, classify_bone

import itertools


def declare_entity_id(key_id_dict, fresh_ids, key=None):
    """
    This function attempts to find the entity ID for the given key in the given
    key_id_dict – generating new keys from fresh_ids as needed.

    If key is not None and if there is existing entity ID in the key_id_dict,
    then the function will return that entity ID.

    If key is None, or if there is no existing entity ID yet, then it will use
    fresh_ids.__next__ (which is expected to be an iterator of unique IDs) to
    create a new entity ID, add it to the key_id_dict (if key is not None), and
    return that new entity ID.
    """
    if key is None:
        # Create a fresh new entity ID without registering. For example, edges
        # have no keys.
        return fresh_ids.__next__()
    else:
        existing_id = key_id_dict.get(key)
        if existing_id is not None:
            return existing_id
        else:
            # Create a fresh new entity ID.
            new_id = fresh_ids.__next__()
            # Add the new entity id to the key_id_dict, so that it is reused
            # next time we look up the given key.
            key_id_dict[key] = new_id
            return new_id


def declare_cluster(
    blender_struct,
    graph_data,
    struct_cluster_id_dict,
    fresh_ids,
    label=None,
):
    """
    If it does not already exist, this function creates a node cluster for the
    given blender_struct (an armature or mesh scene object) and adds it to the
    graph. It returns the entity ID of the cluster.

    The cluster is labeled with the blender_struct’s name.
    An item is added to struct_cluster_id_dict from the blender_struct to the
    new cluster ID.

    If blender_struct is None, then the cluster has no label and nothing is
    added to struct_cluster_id_dict.
    """
    # Get or create a cluster for the blender_struct.
    cluster_id = declare_entity_id(
        key_id_dict=struct_cluster_id_dict,
        fresh_ids=fresh_ids,
        key=blender_struct,
    )

    # If a constraint elsewhere referred to this blender_struct or one of its
    # components, then this blender_struct’s cluster may have already been
    # created. First check if the cluster’s set of child nodes already exists.
    child_node_id_set = graph_data['cluster_nodes_dict'].get(cluster_id)
    child_node_id_set = (
        child_node_id_set
        if child_node_id_set is not None
        # If the the cluster’s set of child nodes does not already exist,
        # create a new empty set.
        else set()
    )

    # Register the cluster (and its child-node set), in case it was newly
    # created. This will do nothing if the cluster already existed.
    graph_data['cluster_nodes_dict'][cluster_id] = child_node_id_set

    # By default, the cluster’s label is the blender_struct’s name, if the
    # blender_struct is not None.
    if label is None and blender_struct is not None:
        label = blender_struct.name

    graph_data['entity_label_dict'][cluster_id] = label

    return cluster_id


def declare_node(
    blender_struct,
    graph_data,
    struct_entity_id_dict,
    fresh_ids,
    cluster_id=None,
    label=None,
    categories=None,
):
    """
    If it does not already exist, this function creates a node for the given
    blender_struct (whether it be a scene object, a bone, or a vertex group)
    and adds it to the graph. It also can assign a given label or categories to
    that node, and it can add the node to a given cluster_id’s set of contained
    nodes (the cluster must already have been declared). If cluster_id is None,
    then the node will instead be added to the graph’s “free” nodes, which
    belong to no node cluster in the graph.

    It returns the entity ID of the node.
    """

    # Get or create a node for the blender_struct.
    node_id = declare_entity_id(
        key_id_dict=struct_entity_id_dict,
        fresh_ids=fresh_ids,
        key=blender_struct,
    )

    if cluster_id is not None:
        # In this case, register the node in the given cluster’s set of
        # contained nodes.
        graph_data['cluster_nodes_dict'][cluster_id].add(node_id)
    else:
        # In this case, add the node to the set of free nodes.
        graph_data['free_nodes'].add(node_id)

    # Register the label for the node.
    if label is not None:
        graph_data['entity_label_dict'][node_id] = label

    # Register the categories for the node.
    if categories is not None:
        graph_data['entity_categories_dict'][node_id] = categories

    return node_id


def declare_edge(
    blender_struct,
    origin_node_id,
    destination_node_id,
    graph_data,
    struct_entity_id_dict,
    fresh_ids,
    label=None,
    categories=None,
):
    """
    If it does not already exist, this function creates an edge between the two
    given node IDs. It also can assign a given label or categories to that
    edge. It returns the entity ID of the edge.
    """

    # Get or create an entity.
    edge_id = declare_entity_id(
        key_id_dict=struct_entity_id_dict,
        fresh_ids=fresh_ids,
        key=blender_struct,
    )

    # Register the new edge’s tuple.
    graph_data['edge_tuple_dict'][edge_id] = (
        origin_node_id, destination_node_id,
    )

    # Register the label for the edge.
    if label is not None:
        graph_data['entity_label_dict'][edge_id] = label

    # Register the categories for the edge.
    if categories is not None:
        graph_data['entity_categories_dict'][edge_id] = categories

    return edge_id


def declare_free_node(
    blender_struct,
    graph_data,
    struct_entity_id_dict,
    struct_cluster_id_dict,
    fresh_ids,
):
    """
    If it does not already exist, this function creates a “free” node for the
    given blender_struct that does not belong to any cluster in the graph. The
    blender_struct must not be an armature or mesh scene object, since those
    correspond to clusters and their head nodes.

    This function returns the entity ID of the free node.

    The node will be labeled with the blender_struct’s name, and it will be in
    the 'free' category.
    """

    # Get or create a free node for the blender_struct.
    node_id = declare_node(
        blender_struct=blender_struct,
        graph_data=graph_data,
        struct_entity_id_dict=struct_entity_id_dict,
        fresh_ids=fresh_ids,
        label=blender_struct.name,
        categories=('free',),
    )

    return node_id


def declare_head_node(
    blender_struct,
    graph_data,
    struct_entity_id_dict,
    struct_cluster_id_dict,
    fresh_ids,
    categories,
):
    """
    If it does not already exist, this function creates a “•” head node for the
    given blender_struct (an armature or mesh scene object) and adds it to the
    blender_struct’s cluster in the graph. (If given blender_struct does not
    already have a cluster, a cluster for it will be created.) It returns the
    entity ID of the head node.

    This “•” head node indicates the blender_struct’s scene-object-level
    relationships. This is because we do not support directly connecting edges
    to or from clusters.

    The “•” head node will have no label.
    """

    # Get or create a cluster for the blender_struct.
    cluster_id = declare_cluster(
        blender_struct=blender_struct,
        graph_data=graph_data,
        struct_cluster_id_dict=struct_cluster_id_dict,
        fresh_ids=fresh_ids,
    )

    # Get or create an head node for the blender_struct.
    head_node_id = declare_node(
        blender_struct=blender_struct,
        graph_data=graph_data,
        struct_entity_id_dict=struct_entity_id_dict,
        fresh_ids=fresh_ids,
        # Thanks to declare_cluster, a set of child nodes for the cluster is
        # guaranteed to exist. Register the head node in the blender_struct’s
        # cluster’s contents.
        cluster_id=cluster_id,
        # Head nodes are unobtrusively labeled with '•'.
        label='•',
        # Head nodes get their own 'head' category.
        categories=categories,
    )

    return head_node_id


def declare_plain_bone_node(
    bone,
    armature_object,
    graph_data,
    struct_entity_id_dict,
    struct_cluster_id_dict,
    fresh_ids,
    right_symmetric_bones_are_excluded,
    is_bone_excluded,
):
    """
    If it does not already exist, this function creates a node for the bone in
    the given armature_object, and it adds the bone to the armature_object’s
    cluster (which is created as needed).

    It might not create a node if the bone is to be excluded from the graph
    (i.e., when is_bone_excluded returns True). In that case, this function
    returns None.

    Otherwise, it always assigns to that node a label (the bone’s name) and
    categories (the bone’s type – as determined by the analyzebones module’s
    classify_bone function – and whether the bone deforms).

    It returns the entity ID of the node, if any bone node was created.

    The fresh_ids argument must be an iterable of new unique entity IDs; see
    declare_entity_id.
    """

    if is_bone_excluded(bone, armature_object):
        # In this case, the bone is excluded as per the given predicate
        # function. Do not add any node for the bone.
        return

    # Classify the given bone by its symmetry.
    bone_type, _, bilateral_bone_name = classify_bone(bone, armature_object)

    if right_symmetric_bones_are_excluded and bone_type == 'right_symmetric':
        # Right-sided symmetric bones ('right_symmetric' type) are generally
        # excluded from the graph, since they are redundant with left-sided
        # symmetric bones ('left_symmetric' type). The only exception is when
        # they are targeted by a constraint belonging to something that is in
        # the graph (like a left-sided bone).
        return

    # Get or create the armature_object’s cluster.
    cluster_id = declare_cluster(
        blender_struct=armature_object,
        graph_data=graph_data,
        struct_cluster_id_dict=struct_cluster_id_dict,
        fresh_ids=fresh_ids,
    )

    # Determine if the bone is a deformation bone.
    bone_deforms = bone.use_deform

    bone_label = (
        bilateral_bone_name
        if bone_type == 'left_symmetric'
        else bone.name
    )

    # Get or create a node for the bone.
    bone_node_id = declare_node(
        blender_struct=bone,
        graph_data=graph_data,
        struct_entity_id_dict=struct_entity_id_dict,
        fresh_ids=fresh_ids,

        # Thanks to declare_cluster, a set of child nodes for the cluster is
        # guaranteed to exist. Register the bone node in the armature’s
        # cluster’s contents.
        cluster_id=cluster_id,

        label=bone_label,

        # The bone node’s categories depend on its bone type and whether it
        # deforms meshes.
        categories=('bone', 'deforming' if bone_deforms else '', bone_type,),
    )

    return bone_node_id


def declare_constrained_bone_node(
    bone,
    armature_object,
    graph_data,
    struct_entity_id_dict,
    struct_cluster_id_dict,
    fresh_ids,
    right_symmetric_bones_are_excluded,
    is_bone_excluded,
):
    """
    This function is like declare_plain_bone_node, except it also also creates
    an edge for each of the bone’s constraints – creating nodes and clusters
    for the constraints’ targets and subtargets as needed.

    It does not add parent relations to any bones. Parent relations are
    declared elsewhere – after all entities to referred by constraints are
    added to the graph – to ensure that there is a parent-relation edge for
    every parent relation existing between any two structs with graph nodes.

    The fresh_ids argument must be an iterable of new unique entity IDs; see
    declare_entity_id.

    For more information, see analyze_rig_graph.
    """

    # Create a labeled, categorized bone node inside the armature_object’s
    # cluster (creating the cluster if necessary).
    bone_node_id = declare_plain_bone_node(
        bone=bone,
        armature_object=armature_object,
        graph_data=graph_data,
        struct_entity_id_dict=struct_entity_id_dict,
        struct_cluster_id_dict=struct_cluster_id_dict,
        fresh_ids=fresh_ids,
        right_symmetric_bones_are_excluded=right_symmetric_bones_are_excluded,
        is_bone_excluded=is_bone_excluded,
    )

    if bone_node_id is None:
        # In this case, the bone is to be excluded from the graph.
        return bone_node_id

    # Only PoseBones contain constraint data, so we will need the PoseBone
    # version of the given bone.
    pose_bone = armature_object.pose.bones[bone.name]

    # Add each of the bone’s PoseBone’s constraints to the graph as an edge.
    declare_constraint_edges(
        origin_node_id=bone_node_id,
        constraints=pose_bone.constraints,
        graph_data=graph_data,
        struct_entity_id_dict=struct_entity_id_dict,
        struct_cluster_id_dict=struct_cluster_id_dict,
        fresh_ids=fresh_ids,
        is_bone_excluded=is_bone_excluded,
        home_armature_object=armature_object,
    )


def declare_armature_entities(
    target,
    subtarget_name,
    graph_data,
    struct_entity_id_dict,
    struct_cluster_id_dict,
    fresh_ids,
    constraints_are_included,
    contained_bones_are_included,
    right_symmetric_bones_are_excluded,
    is_bone_excluded,
):
    """
    See declare_destination_entities. The target must be an armature scene
    object.
    """
    # We switch between two bone-node-declaring functions, depending on whether
    # constraints_are_included is true.
    #
    # When we are analyzing the bone of a user-selected armature scene object,
    # we want to include all of its constraints. In that case,
    # constraints_are_included would be true.
    #
    # When we are analyzing the bone that is merely the destination of a
    # constraint, we do not want to include all of its constraints, or else we
    # will transitively include many more scene objects in the graph than
    # intended. In that case, constraints_are_included would be false.
    declare_bone_node = (
        declare_constrained_bone_node
        if constraints_are_included
        else declare_plain_bone_node
    )

    if subtarget_name:
        # In this case, the constraint’s destination is a bone that is in the
        # armature scene object.
        destination = target.data.bones[subtarget_name]

        # This bone needs to have a node.
        bone_node_id = declare_bone_node(
            bone=destination,
            armature_object=target,
            graph_data=graph_data,
            struct_entity_id_dict=struct_entity_id_dict,
            struct_cluster_id_dict=struct_cluster_id_dict,
            fresh_ids=fresh_ids,
            right_symmetric_bones_are_excluded=(
                right_symmetric_bones_are_excluded
            ),
            is_bone_excluded=is_bone_excluded,
        )

        return bone_node_id

    else:
        # In this case, there is no subtarget: the constraint’s destination is
        # this armature scene object itself.

        # Declare a “•” head node for the armature object inside of its node
        # cluster. This head node will be removed elsewhere if no edge points
        # to or from it. This will also create a new cluster for the armature
        # scene object if it does not yet have a cluster.
        head_node_id = declare_head_node(
            blender_struct=target,
            graph_data=graph_data,
            struct_entity_id_dict=struct_entity_id_dict,
            struct_cluster_id_dict=struct_cluster_id_dict,
            fresh_ids=fresh_ids,
            categories='armature_head'
        )

        # If constraints_are_included is true, then add each of the armature
        # scene object’s object-level constraints to the graph as an edge.
        if constraints_are_included:
            declare_constraint_edges(
                origin_node_id=head_node_id,
                constraints=target.constraints,
                graph_data=graph_data,
                struct_entity_id_dict=struct_entity_id_dict,
                struct_cluster_id_dict=struct_cluster_id_dict,
                fresh_ids=fresh_ids,
                is_bone_excluded=is_bone_excluded,
            )

        # If include_bones is true, then add a node for each bone to the
        # cluster (as well as an edge for each constraint – creating nodes and
        # clusters for the constraints’ targets and subtargets as needed). Bone
        # data is assumed to be synchronized with Edit Mode using
        # update_from_editmode.
        if contained_bones_are_included:
            for bone in target.data.bones:
                declare_bone_node(
                    bone=bone,
                    armature_object=target,
                    graph_data=graph_data,
                    struct_entity_id_dict=struct_entity_id_dict,
                    struct_cluster_id_dict=struct_cluster_id_dict,
                    fresh_ids=fresh_ids,
                    right_symmetric_bones_are_excluded=(
                        right_symmetric_bones_are_excluded
                    ),
                    is_bone_excluded=is_bone_excluded,
                )

        # Return the armature’s “•” head node ID.
        return head_node_id


def declare_mesh_entities(
    target,
    subtarget_name,
    graph_data,
    struct_entity_id_dict,
    struct_cluster_id_dict,
    fresh_ids,
    constraints_are_included,
    is_bone_excluded,
):
    """
    See declare_destination_entities. The target must be a mesh scene object.
    """
    # Get or create the mesh scene object’s node cluster.
    cluster_id = declare_cluster(
        blender_struct=target,
        graph_data=graph_data,
        struct_cluster_id_dict=struct_cluster_id_dict,
        fresh_ids=fresh_ids,
    )

    # Declare a “•” head node for the mesh scene object, inside of the
    # mesh’s node cluster. This head node will be removed elsewhere if no
    # edge points to or from it.
    head_node_id = declare_head_node(
        blender_struct=target,
        graph_data=graph_data,
        struct_entity_id_dict=struct_entity_id_dict,
        struct_cluster_id_dict=struct_cluster_id_dict,
        fresh_ids=fresh_ids,
        categories='mesh_head',
    )

    if subtarget_name:
        # In this case, the constraint’s destination is a vertex group.
        destination = target.vertex_groups[subtarget_name]

        # Get or create the vertex group’s node.
        vertex_group_node_id = declare_node(
            blender_struct=destination,
            graph_data=graph_data,
            struct_entity_id_dict=struct_entity_id_dict,
            fresh_ids=fresh_ids,

            # Thanks to declare_cluster, a set of child nodes for the mesh’s
            # cluster is guaranteed to exist. Register the bone node in the
            # mesh’s cluster’s contents.
            cluster_id=cluster_id,

            label=subtarget_name,
            categories='vertex_group',
        )

        return vertex_group_node_id

    else:
        # In this case, there is no subtarget: the constraint’s destination is
        # this mesh scene object itself.

        # If constraints_are_included is true, then add each of the mesh scene
        # object’s constraints to the graph as an edge.
        if constraints_are_included:
            declare_constraint_edges(
                origin_node_id=head_node_id,
                constraints=target.constraints,
                graph_data=graph_data,
                struct_entity_id_dict=struct_entity_id_dict,
                struct_cluster_id_dict=struct_cluster_id_dict,
                fresh_ids=fresh_ids,
                is_bone_excluded=is_bone_excluded,
            )

        return head_node_id


def declare_destination_entities(
    target,
    subtarget_name,
    graph_data,
    struct_entity_id_dict,
    struct_cluster_id_dict,
    fresh_ids,
    contained_bones_are_included,
    constraints_are_included,
    right_symmetric_bones_are_excluded,
    is_bone_excluded,
):
    """
    If it does not already exist, this function creates a node for the
    destination specified by the given target scene object and subtarget_name.
    It also adds that node to the target scene object’s cluster if appropriate
    (i.e., when the target is an armature or mesh scene object).

    If include_bones is true, and if the destination is an armature scene
    object, then this function will also declare any bones that the target
    contains.
    """
    target_type = target.type

    if target_type == 'ARMATURE':
        return declare_armature_entities(
            target=target,
            subtarget_name=subtarget_name,
            graph_data=graph_data,
            struct_entity_id_dict=struct_entity_id_dict,
            struct_cluster_id_dict=struct_cluster_id_dict,
            fresh_ids=fresh_ids,
            contained_bones_are_included=contained_bones_are_included,
            right_symmetric_bones_are_excluded=(
                right_symmetric_bones_are_excluded
            ),
            is_bone_excluded=is_bone_excluded,
            constraints_are_included=constraints_are_included,
        )

    elif target_type == 'MESH':
        return declare_mesh_entities(
            target=target,
            subtarget_name=subtarget_name,
            graph_data=graph_data,
            struct_entity_id_dict=struct_entity_id_dict,
            struct_cluster_id_dict=struct_cluster_id_dict,
            fresh_ids=fresh_ids,
            constraints_are_included=constraints_are_included,
            is_bone_excluded=is_bone_excluded,
        )

    else:
        # In this case, the target is some other type of scene object, like an
        # empty or a light, so we declare one free node for that scene object.
        free_node_id = declare_free_node(
            blender_struct=target,
            graph_data=graph_data,
            struct_entity_id_dict=struct_entity_id_dict,
            struct_cluster_id_dict=struct_cluster_id_dict,
            fresh_ids=fresh_ids,
        )

        # If constraints_are_included is true, then add each of the mesh scene
        # object’s constraints to the graph as an edge.
        if constraints_are_included:
            declare_constraint_edges(
                origin_node_id=free_node_id,
                constraints=target.constraints,
                graph_data=graph_data,
                struct_entity_id_dict=struct_entity_id_dict,
                struct_cluster_id_dict=struct_cluster_id_dict,
                fresh_ids=fresh_ids,
                is_bone_excluded=is_bone_excluded,
            )

        return free_node_id


def declare_constraint_edges(
    origin_node_id,
    constraints,
    graph_data,
    struct_entity_id_dict,
    struct_cluster_id_dict,
    fresh_ids,
    is_bone_excluded,
    home_armature_object=None,
):
    """
    If it does not already exist, this function creates an edge for each of the
    given constraints from the given origin_node_id to each constraint’s
    destination (as defined by its target and subtarget). It also adds nodes
    and node clusters as necessary for each destination.

    Supply home_armature_object when the constraints belong to a bone in that
    home_armature_object. It is used to check whether to exclude right-sided
    symmetric bones.
    """
    for c in constraints:
        # Not all constraints have targets – e.g., Limit Rotation. They do not
        # appear in the graph.
        target = getattr(c, 'target', None)

        if target is None:
            break

        # The subtarget attribute is a simple string referring to the
        # component’s name (whether it be the name of an armature’s bone or of
        # a mesh’s vertex group).
        subtarget_name = getattr(c, 'subtarget', None)

        # Find and declare the destination’s node (and its node cluster if the
        # destination is an armature or mesh scene object). This evaluates to
        # None if the destination is to be excluded from the graph (e.g., it is
        # a right-sided symmetrical node in the same home_armature_object as
        # the constraint’s owner bone).
        destination_node_id = declare_destination_entities(
            target=target,
            subtarget_name=subtarget_name,
            graph_data=graph_data,
            struct_entity_id_dict=struct_entity_id_dict,
            struct_cluster_id_dict=struct_cluster_id_dict,
            fresh_ids=fresh_ids,

            # When we are analyzing the mere destination of a constraint, we do
            # not want to automatically include all of its constraints, or else
            # we will transitively include many more scene objects in the graph
            # than intended.
            constraints_are_included=False,

            # If the destination is an armature scene object, then we do not
            # want to automatically include all of its contained bones.
            contained_bones_are_included=False,

            # If a home_armature_object is given (i.e., the given constraints
            # belong to a a bone that belongs to the home_armature_object), and
            # if the destination is a right-sided symmetric bone, then we would
            # exclude this constraint from the graph only if that destination
            # bone belongs to the same home_armature_object. We do not want to
            # exclude constraints that point to right-sided symmetric bones in
            # outside armature objects (i.e., constraints that cross between
            # sides). Otherwise, no version of those constraints, whichever
            # side they start on, would appear in the graph.
            right_symmetric_bones_are_excluded=(
                home_armature_object is not None
                and target is home_armature_object
            ),

            is_bone_excluded=is_bone_excluded,
        )

        if destination_node_id is not None:
            # In this case the destination node has been declared and not
            # excluded from the graph, and an edge pointing to that destination
            # will also be declared.
            declare_edge(
                blender_struct=c,
                origin_node_id=origin_node_id,
                destination_node_id=destination_node_id,
                graph_data=graph_data,
                struct_entity_id_dict=struct_entity_id_dict,
                fresh_ids=fresh_ids,
                # The new edge’s label is its constraint’s name.
                label=c.name,
                # The new edge’s category is constraint.
                categories=('constraint',),
            )


def declare_parent_relation_edge(
    blender_struct,
    graph_data,
    struct_entity_id_dict,
    fresh_ids,
):
    """
    If the given blender_struct has a parent (e.g., the parent Bone of a Bone
    or the parent scene object of a scene object), and if both blender_struct
    and its parent have corresponding nodes in the graph, then add an edge
    between the two nodes. The edge will have no label, and it will have the
    category 'parent'. The function returns the entity ID of the new edge, if
    any, or None.

    We draw an edge to a parent only if it already exists in the graph, in
    order to prevent that parent from recursively causing its own parent edges
    to be added. If it does not already exist, then no edge node is created.
    """
    entity_id = struct_entity_id_dict[blender_struct]

    if entity_id is None:
        # In this case, the given blender_struct for some reason does not have
        # an existing node, so we cannot add any parent edge for it.
        return

    parent_struct = getattr(blender_struct, 'parent', None)
    parent_relationship_type = getattr(blender_struct, 'parent_type', None)
    parent_bone_name = getattr(blender_struct, 'parent_bone', None)

    parent_struct_type = getattr(parent_struct, 'type', None)

    parent_relationship_targets_bone = (
        parent_struct_type == 'ARMATURE'
        and parent_relationship_type == 'BONE'
    )

    # If the parent relationship is a Bone type rather than an Object type,
    # then its destination is a specific bone.
    parent_bone = (
        parent_struct.data.bones[parent_bone_name]
        if parent_relationship_targets_bone
        else None
    )

    parent_bone_node_id = (
        struct_entity_id_dict.get(parent_bone, None)
        if parent_bone is not None
        else None
    )

    # We draw an edge to a parent bone only if it already exists in the graph,
    # in order to prevent that bone from recursively causing its own parent
    # edges to be added. If it does not already exist, then no edge node is
    # created.
    parent_node_id = (
        parent_bone_node_id
        if parent_bone_node_id is not None
        else struct_entity_id_dict.get(parent_struct, None)
    )

    if parent_node_id is not None:
        # Create an edge for the parent relation. (Parent relations do
        # not have keys, since there is no single Blender structure
        # corresponding to them, so declare_entity_id is not passed a key.)
        declare_edge(
            blender_struct=None,
            origin_node_id=entity_id,
            destination_node_id=parent_node_id,
            graph_data=graph_data,
            struct_entity_id_dict=struct_entity_id_dict,
            fresh_ids=fresh_ids,
            categories=('parent',),
        )


def is_bone_entity(entity_id, entity_categories_dict):
    """
    Returns a boolean on whether the given entity_id has a 'bone' category in
    the entity_categories_dict.
    """
    return 'bone' in entity_categories_dict[entity_id]


def declare_root_bone_style(
    blender_struct,
    graph_data,
    struct_entity_id_dict,
):
    """
    Nodes of bones with no parent bone are marked with the 'root_bone' category
    instead. (If a given bone has a parent bone, then even if the parent bone
    was excluded from the graph, then the given bone is not a root bone.)
    """
    entity_categories_dict = graph_data['entity_categories_dict']

    parent_struct = getattr(blender_struct, 'parent', None)

    entity_id = struct_entity_id_dict[blender_struct]

    blender_struct_is_root_bone = (
        parent_struct is None
        and is_bone_entity(entity_id, entity_categories_dict)
    )

    if blender_struct_is_root_bone:
        entity_categories_dict[entity_id] = (
            *entity_categories_dict[entity_id],
            'root',
        )


def is_unused_head_node(node_id, cluster_id, graph_data):
    """
    This function returns whether the head node with the given node_id is
    unused: if no edge uses it as its origin or destination and if it is not
    the only single node in its cluster (given by cluster_id).
    """
    # cluster_id may be None if the node is an empty scene object, a camera
    # scene object, etc.
    if node_id is None or cluster_id is None:
        return False

    # This function considers a node to be a head node if it has the 'head'
    # category. If node_id or cluster_id is None, then this function returns
    # False.
    if 'head' not in graph_data['entity_categories_dict'].get(node_id):
        return False

    # We do not count head nodes that are the sole members of their clusters as
    # unused. Otherwise, selecting only a mesh scene object with no vertex
    # groups – or an armature scene object with no bones – would generate an
    # empty graph.
    cluster_nodes = graph_data['cluster_nodes_dict'].get(cluster_id)
    if cluster_nodes is not None and len(cluster_nodes) == 1:
        return False

    # In this case, these are other nodes in the same cluster. Check whether
    # the head node is connected to anything else with an edge.
    edge_tuples = graph_data['edge_tuple_dict'].values()
    for origin_node_id, destination_node_id in edge_tuples:
        if node_id == origin_node_id or node_id == destination_node_id:
            return False

    return True


def remove_node_if_unused_head(
    blender_struct,
    graph_data,
    struct_entity_id_dict,
    struct_cluster_id_dict,
):
    """
    This function removes the node of the given blender_struct from the graph
    if it is an unused head node of a cluster, as defined by
    is_unused_head_node.
    """
    cluster_id = struct_cluster_id_dict.get(blender_struct)
    node_id = struct_entity_id_dict.get(blender_struct)

    if is_unused_head_node(node_id, cluster_id, graph_data):
        graph_data['cluster_nodes_dict'][cluster_id].remove(node_id)
        del struct_entity_id_dict[blender_struct]


def initialize_graph_data():
    """
    This function analyzes the given scene objects and returns data
    representing a graph of their relationships. The graph contains clusters
    containing nodes. Edges connect nodes to one another (even if the nodes are
    from different clusters). Clusters, nodes, and edges are all called
    “entities”. Entities are represented by unique IDs (arbitrary integers or
    strings in the same namespace), and they each can have one label and a
    tuple of categories. Categories are also entities with their own IDs.

    This function returns a graph-data dictionary with the following items.

    free_nodes: A set of node IDs that do not belong to any cluster.

    cluster_nodes_dict: A dictionary from each cluster ID to a set of the node
    IDs that the cluster contains. There is one node in each cluster that
    represents the armature scene object itself. All other nodes each represent
    one bone in its cluster’s armature.

    edge_tuple_dict: A dictionary from each edge ID to its tuple pair
    (origin_node_id, destination_node_id). Each edge represents either a parent
    relationship or a constraint between any two Blender scene objects,
    PoseBones, or vertex groups.

    entity_label_dict: A dictionary from each entity ID to its label, if any.

    entity_categories_dict: A dictionary from each entity ID to a tuple of
    category names.

    Clusters, nodes, and edges have incrementing integers as their IDs.

    Category names are any of the following strings:

    'asymmetric': These are nodes for bones that do not have any paired
    opposite-sided bone.

    'left_symmetric': These are nodes for left-sided bones that each has
    exactly one paired right-sided bone, which in turn must share the same
    relationship names, types, targets, and parameters.

    'right_symmetric': These are nodes for right-sided bones that each has
    exactly one paired left-sided bone, which in turn must share the same
    relationship names, types, targets, and parameters.

    'antisymmetric': These are nodes for left- or right-sided bones that either
    do not have a paired opposite-sided bone or do not completely match their
    paired opposite-sided bone (e.g., if their parents do not match or if
    either of them have a constraint that is missing or different in the other
    bone). See the analyzebones module for more information.

    'head': These are head nodes for armatures and meshes. These always have no
    label. (We use these to express scene-object-level relationships, because
    we cannot connect edges directly to clusters.)

    'constraint': These are edges that represent constraints, rather than
    parent relationships.
    """

    return {
        'free_nodes': set(),
        'cluster_nodes_dict': {},
        'edge_tuple_dict': {},
        'entity_label_dict': {},
        'entity_categories_dict': {},
    }


def analyze_rig_graph(blender_structs, is_bone_excluded):
    """
    This function analyzes the given blender_structs (such as armature scene
    objects or bones) and returns data representing a graph of their
    relationships. See initialize_graph_data for more information on the
    returned graph data.
    """
    # This iterator indefinitely yields consecutive integers starting from 0,
    # with its __next__ method.
    fresh_ids = itertools.count()

    # We will temporarily need to look up existing entity IDs for each scene
    # object, PoseBone, or vertex groups that we add to the graph.
    struct_entity_id_dict = {}

    # We will also need to look up existing cluster IDs for each armature
    # scene object.
    struct_cluster_id_dict = {}

    graph_data = initialize_graph_data()

    # Add clusters, nodes, and edges for each Blender scene object given in the
    # arguments, as well as any scene objects to which their constraints refer.
    # We do not yet create edges for parent relations.
    for bs in blender_structs:
        declare_destination_entities(
            # The target object is each selected scene object.
            target=bs,
            # We want to declare all bones in selected armature scene objects,
            # so we do not specify a specific subtarget here.
            subtarget_name=None,

            graph_data=graph_data,
            struct_entity_id_dict=struct_entity_id_dict,
            struct_cluster_id_dict=struct_cluster_id_dict,
            fresh_ids=fresh_ids,

            # We want to include the constraints on the selected scene object
            # (as well as the constraints of any bones it contains).
            constraints_are_included=True,

            # We want to include the bones of selected armature scene objects…
            contained_bones_are_included=True,

            # …except that we want to exclude right-sided bones from selected
            # armature scene objects.
            right_symmetric_bones_are_excluded=True,

            is_bone_excluded=is_bone_excluded,
        )

    # We separately create parent relations for each Blender structure that has
    # a node in the graph (either due to being directly supplied in the
    # arguments or being referred to by one of the arguments). This ensures
    # that parent relations between all referred scene objects (even those that
    # were not directly supplied in the arguments).
    for blender_struct in struct_entity_id_dict:
        declare_parent_relation_edge(
            blender_struct=blender_struct,
            graph_data=graph_data,
            struct_entity_id_dict=struct_entity_id_dict,
            fresh_ids=fresh_ids,
        )

    # We mark bones with no parent bone as root bones. (Whether that parent has
    # been included in the graph_data is irrelevant here.)
    for blender_struct in struct_entity_id_dict:
        declare_root_bone_style(
            blender_struct=blender_struct,
            graph_data=graph_data,
            struct_entity_id_dict=struct_entity_id_dict,
        )

    # We remove unused “•” head nodes from each cluster (each of which
    # corresponds to an armature scene object or a mesh scene object).
    for blender_struct in struct_cluster_id_dict:
        remove_node_if_unused_head(
            blender_struct=blender_struct,
            graph_data=graph_data,
            struct_entity_id_dict=struct_entity_id_dict,
            struct_cluster_id_dict=struct_cluster_id_dict,
        )

    return graph_data


def create_legend_data():
    """
    This function creates a graph representing an explanatory legend.
    """
    # This iterator indefinitely yields consecutive integers starting from 0,
    # with its __next__ method.
    fresh_ids = itertools.count()

    # We will temporarily need to look up existing entity IDs for each scene
    # object, PoseBone, or vertex groups that we add to the graph.
    struct_entity_id_dict = {}

    # We will also need to look up existing cluster IDs for each armature
    # scene object.
    struct_cluster_id_dict = {}

    graph_data = initialize_graph_data()

    cluster_id = declare_cluster(
        blender_struct=None,
        graph_data=graph_data,
        struct_cluster_id_dict=struct_cluster_id_dict,
        fresh_ids=fresh_ids,
        label='Legend',
    )

    parent_node_id = declare_node(
        blender_struct=None,
        graph_data=graph_data,
        struct_entity_id_dict=struct_entity_id_dict,
        fresh_ids=fresh_ids,
        cluster_id=cluster_id,
        label='Parent',
    )

    child_node_id = declare_node(
        blender_struct=None,
        graph_data=graph_data,
        struct_entity_id_dict=struct_entity_id_dict,
        fresh_ids=fresh_ids,
        cluster_id=cluster_id,
        label='Child',
    )

    declare_edge(
        blender_struct=None,
        origin_node_id=child_node_id,
        destination_node_id=parent_node_id,
        graph_data=graph_data,
        struct_entity_id_dict=struct_entity_id_dict,
        fresh_ids=fresh_ids,
        categories=('parent',),
    )

    subject_node_id = declare_node(
        blender_struct=None,
        graph_data=graph_data,
        struct_entity_id_dict=struct_entity_id_dict,
        fresh_ids=fresh_ids,
        cluster_id=cluster_id,
        label='Subject',
    )

    target_node_id = declare_node(
        blender_struct=None,
        graph_data=graph_data,
        struct_entity_id_dict=struct_entity_id_dict,
        fresh_ids=fresh_ids,
        cluster_id=cluster_id,
        label='Target',
    )

    declare_edge(
        blender_struct=None,
        origin_node_id=subject_node_id,
        destination_node_id=target_node_id,
        graph_data=graph_data,
        struct_entity_id_dict=struct_entity_id_dict,
        fresh_ids=fresh_ids,
        label='Constraint',
        categories=('constraint',),
    )

    deforming_bone_node_id = declare_node(
        blender_struct=None,
        graph_data=graph_data,
        struct_entity_id_dict=struct_entity_id_dict,
        fresh_ids=fresh_ids,
        label='Deforming Bone',
        cluster_id=cluster_id,
        categories=('bone', 'deforming'),
    )

    root_bone_node_id = declare_node(
        blender_struct=None,
        graph_data=graph_data,
        struct_entity_id_dict=struct_entity_id_dict,
        fresh_ids=fresh_ids,
        label='Root',
        cluster_id=cluster_id,
        categories=('bone', 'root'),
    )

    # Invisible edges are needed to group nodes in the legend in multiple
    # columns and rows.
    declare_edge(
        blender_struct=None,
        origin_node_id=deforming_bone_node_id,
        destination_node_id=root_bone_node_id,
        graph_data=graph_data,
        struct_entity_id_dict=struct_entity_id_dict,
        fresh_ids=fresh_ids,
        categories=('invisible',),
    )

    symmetric_bone_node_id = declare_node(
        blender_struct=None,
        graph_data=graph_data,
        struct_entity_id_dict=struct_entity_id_dict,
        fresh_ids=fresh_ids,
        label=f'Symmetric Bone.{mirror_symbol}',
        cluster_id=cluster_id,
        categories=('bone',),
    )

    antisymmetric_bone_node_id = declare_node(
        blender_struct=None,
        graph_data=graph_data,
        struct_entity_id_dict=struct_entity_id_dict,
        fresh_ids=fresh_ids,
        label='Symmetry-Breaking Bone',
        cluster_id=cluster_id,
        categories=('bone', 'antisymmetric'),
    )

    declare_edge(
        blender_struct=None,
        origin_node_id=symmetric_bone_node_id,
        destination_node_id=antisymmetric_bone_node_id,
        graph_data=graph_data,
        struct_entity_id_dict=struct_entity_id_dict,
        fresh_ids=fresh_ids,
        categories=('invisible',),
    )

    return graph_data
