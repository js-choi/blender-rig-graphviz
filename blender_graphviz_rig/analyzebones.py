# This module is licensed by its authors under the GNU Affero General Public
# License 3.0.

"""
This module analyzes Blender bones, determining whether their names indicate
that they are left- or right-sided and whether their names and their
constraints are symmetrical.

These functions assume that all scene objects’ data-blocks and pose data are up
to date (by using `update_from_editmode`_). In particular, they assume that
armatures’ Bones and PoseBones are synchronized.

.. _update_from_editmode: https://docs.blender.org/api/latest/bpy.types.Object.html#bpy.types.Object.update_from_editmode
""" # noqa

import re

# We use a symbol to indicate whether bones are symmetrically mirrored.
mirror_symbol = '↔'


def strip_numeric_suffix(bone_name):
    """
    This function strips any numeric suffix from the bone name.
    """
    return re.sub(r'\.\d+$', '', bone_name)


name_numeric_suffix_pattern = re.compile(r'\.\d+$')


def get_name_numeric_suffix(name):
    """
    This function gets the numeric suffix, if any, from the given name. For
    example, inputting 'blah.001' would return '.001'. If there is no numeric
    suffix, then this function returns an empty string.
    """
    m = name_numeric_suffix_pattern.search(name)
    if m:
        return m.group(0)
    else:
        return ''


# The following patterns are based on Blender’s behavior for bone-name
# symmetry, which uses the letter case of only the word’s first two letters.

# “RIGHT”, “RIght”, “RIghT”, etc. are all equivalent to all-caps “RIGHT”.
right_suffix_all_caps_pattern = re.compile(r'RI[gG][hH][tT]$')
# “Right”, “RiGHT”, “RighT”, etc. are all equivalent to capitalized “Right”.
right_suffix_capitalized_pattern = re.compile(r'Ri[gG][hH][tT]$')
# “right”, “rIGHT”, “rIghT”, etc. are all equivalent to lowercase “right”.
right_suffix_lowercase_pattern = re.compile(r'r[iI][gG][hH][tT]$')

# Similar rules apply for the following patterns.
left_suffix_all_caps_pattern = re.compile(r'LE[fF][tT]$')
left_suffix_capitalized_pattern = re.compile(r'Le[fF][tT]$')
left_suffix_lowercase_pattern = re.compile(r'l[eE][fF][tT]$')

right_prefix_all_caps_pattern = re.compile(r'^RI[gG][hH][tT]')
right_prefix_capitalized_pattern = re.compile(r'^Ri[gG][hH][tT]')
right_prefix_lowercase_pattern = re.compile(r'^ri[gG][hH][tT]')

left_prefix_all_caps_pattern = re.compile(r'^LE[fF][tT]')
left_prefix_capitalized_pattern = re.compile(r'^Le[fF][tT]')
left_prefix_lowercase_pattern = re.compile(r'^l[eE][fF][tT]')

right_word_length = len('right')
left_word_length = len('left')


def parse_bone_name_stem(bone_name_stem):
    """
    See parse_sided_bone_name.
    """
    # The following branches handle when there is a side word at the end of the
    # bone_name_stem. In these cases, any side word at the beginning of the
    # bone_name_stem is ignored.

    # The bone_name_stem ends with a variant of “.R”.

    if bone_name_stem.endswith(('_r', '.r', '-r', ' r')):
        bone_side = 'right'
        bone_name_root = bone_name_stem[:-1]
        opposite_bone_name_stem = bone_name_root + 'l'
        bilateral_bone_name_stem = bone_name_root + mirror_symbol
        return (bone_side, opposite_bone_name_stem, bilateral_bone_name_stem)

    elif bone_name_stem.endswith(('_R', '.R', '-R', ' R')):
        bone_side = 'right'
        bone_name_root = bone_name_stem[:-1]
        opposite_bone_name_stem = bone_name_root + 'L'
        bilateral_bone_name_stem = bone_name_root + mirror_symbol
        return (bone_side, opposite_bone_name_stem, bilateral_bone_name_stem)

    # The bone_name_stem ends with a variant of “.L”.

    elif bone_name_stem.endswith(('_l', '.l', '-l', ' l')):
        bone_side = 'left'
        bone_name_root = bone_name_stem[:-1]
        opposite_bone_name_stem = bone_name_root + 'r'
        bilateral_bone_name_stem = bone_name_root + mirror_symbol
        return (bone_side, opposite_bone_name_stem, bilateral_bone_name_stem)

    elif bone_name_stem.endswith(('_L', '.L', '-L', ' L')):
        bone_side = 'left'
        bone_name_root = bone_name_stem[:-1]
        opposite_bone_name_stem = bone_name_root + 'R'
        bilateral_bone_name_stem = bone_name_root + mirror_symbol
        return (bone_side, opposite_bone_name_stem, bilateral_bone_name_stem)

    # The bone_name_stem ends with a variant of “Right”.

    elif right_suffix_all_caps_pattern.search(bone_name_stem):
        bone_side = 'right'
        bone_name_root = bone_name_stem[:-right_word_length]
        opposite_bone_name_stem = bone_name_root + 'LEFT'
        bilateral_bone_name_stem = bone_name_root + mirror_symbol
        return (bone_side, opposite_bone_name_stem, bilateral_bone_name_stem)

    elif right_suffix_capitalized_pattern.search(bone_name_stem):
        bone_side = 'right'
        bone_name_root = bone_name_stem[:-right_word_length]
        opposite_bone_name_stem = bone_name_root + 'Left'
        bilateral_bone_name_stem = bone_name_root + mirror_symbol
        return (bone_side, opposite_bone_name_stem, bilateral_bone_name_stem)

    elif right_suffix_lowercase_pattern.search(bone_name_stem):
        bone_side = 'right'
        bone_name_root = bone_name_stem[:-right_word_length]
        opposite_bone_name_stem = bone_name_root + 'left'
        bilateral_bone_name_stem = bone_name_root + mirror_symbol
        return (bone_side, opposite_bone_name_stem, bilateral_bone_name_stem)

    # The bone_name_stem ends with a variant of “Left”.

    elif left_suffix_all_caps_pattern.search(bone_name_stem):
        bone_side = 'left'
        bone_name_root = bone_name_stem[:-left_word_length]
        opposite_bone_name_stem = bone_name_root + 'RIGHT'
        bilateral_bone_name_stem = bone_name_root + mirror_symbol
        return (bone_side, opposite_bone_name_stem, bilateral_bone_name_stem)

    elif left_suffix_capitalized_pattern.search(bone_name_stem):
        bone_side = 'left'
        bone_name_root = bone_name_stem[:-left_word_length]
        opposite_bone_name_stem = bone_name_root + 'Right'
        bilateral_bone_name_stem = bone_name_root + mirror_symbol
        return (bone_side, opposite_bone_name_stem, bilateral_bone_name_stem)

    elif left_suffix_lowercase_pattern.search(bone_name_stem):
        bone_side = 'left'
        bone_name_root = bone_name_stem[:-left_word_length]
        opposite_bone_name_stem = bone_name_root + 'right'
        bilateral_bone_name_stem = bone_name_root + mirror_symbol
        return (bone_side, opposite_bone_name_stem, bilateral_bone_name_stem)

    # The following branches handle when there is no side word at the end of
    # the bone_name, but there is a side word at the beginning of the
    # bone_name.

    # The bone_name_stem starts with a variant of “R.”.

    elif bone_name_stem.startswith(('R_', 'R.', 'R-', 'R ')):
        bone_side = 'right'
        bone_name_root = bone_name_stem[1:]
        opposite_bone_name_stem = 'L' + bone_name_root
        bilateral_bone_name_stem = mirror_symbol + bone_name_root
        return (bone_side, opposite_bone_name_stem, bilateral_bone_name_stem)

    elif bone_name_stem.startswith(('r_', 'r.', 'r-', 'r ')):
        bone_side = 'right'
        bone_name_root = bone_name_stem[1:]
        opposite_bone_name_stem = 'l' + bone_name_root
        bilateral_bone_name_stem = mirror_symbol + bone_name_root
        return (bone_side, opposite_bone_name_stem, bilateral_bone_name_stem)

    # The bone_name_stem starts with a variant of “L.”.

    elif bone_name_stem.startswith(('L_', 'L.', 'L-', 'L ')):
        bone_side = 'left'
        bone_name_root = bone_name_stem[1:]
        opposite_bone_name_stem = 'R' + bone_name_root
        bilateral_bone_name_stem = mirror_symbol + bone_name_root
        return (bone_side, opposite_bone_name_stem, bilateral_bone_name_stem)

    elif bone_name_stem.startswith(('l_', 'l.', 'l-', 'l ')):
        bone_side = 'left'
        bone_name_root = bone_name_stem[1:]
        opposite_bone_name_stem = 'r' + bone_name_root
        bilateral_bone_name_stem = mirror_symbol + bone_name_root
        return (bone_side, opposite_bone_name_stem, bilateral_bone_name_stem)

    # The bone_name_stem starts with a variant of “Right”.

    elif right_prefix_all_caps_pattern.search(bone_name_stem):
        bone_side = 'right'
        bone_name_root = bone_name_stem[right_word_length:]
        opposite_bone_name_stem = 'LEFT' + bone_name_root
        bilateral_bone_name_stem = mirror_symbol + bone_name_root
        return (bone_side, opposite_bone_name_stem, bilateral_bone_name_stem)

    elif right_prefix_capitalized_pattern.search(bone_name_stem):
        bone_side = 'right'
        bone_name_root = bone_name_stem[right_word_length:]
        opposite_bone_name_stem = 'Left' + bone_name_root
        bilateral_bone_name_stem = mirror_symbol + bone_name_root
        return (bone_side, opposite_bone_name_stem, bilateral_bone_name_stem)

    elif right_prefix_lowercase_pattern.search(bone_name_stem):
        bone_side = 'right'
        bone_name_root = bone_name_stem[right_word_length:]
        opposite_bone_name_stem = 'left' + bone_name_root
        bilateral_bone_name_stem = mirror_symbol + bone_name_root
        return (bone_side, opposite_bone_name_stem, bilateral_bone_name_stem)

    # The bone_name_stem starts with a variant of “Left”.

    elif left_prefix_all_caps_pattern.search(bone_name_stem):
        bone_side = 'left'
        bone_name_root = bone_name_stem[left_word_length:]
        opposite_bone_name_stem = 'RIGHT' + bone_name_root
        bilateral_bone_name_stem = mirror_symbol + bone_name_root
        return (bone_side, opposite_bone_name_stem, bilateral_bone_name_stem)

    elif left_prefix_capitalized_pattern.search(bone_name_stem):
        bone_side = 'left'
        bone_name_root = bone_name_stem[left_word_length:]
        opposite_bone_name_stem = 'Right' + bone_name_root
        bilateral_bone_name_stem = mirror_symbol + bone_name_root
        return (bone_side, opposite_bone_name_stem, bilateral_bone_name_stem)

    elif left_prefix_lowercase_pattern.search(bone_name_stem):
        bone_side = 'left'
        bone_name_root = bone_name_stem[left_word_length:]
        opposite_bone_name_stem = 'right' + bone_name_root
        bilateral_bone_name_stem = mirror_symbol + bone_name_root
        return (bone_side, opposite_bone_name_stem, bilateral_bone_name_stem)

    # Otherwise, this bone_name_stem has no side.
    return (None, bone_name_stem, bone_name_stem)


def parse_sided_bone_name(bone_name):
    """
    If the given bone_name has a left- or right-side, then this function
    returns a tuple (bone_side, opposite_bone_name, bilateral_bone_name_stem),
    where bone_side is either 'left' or 'right', opposite_bone_name is the
    opposite-sided version of bone_name, and bilateral_bone_name is bone_name
    but with the side replaced by the symbol mirror_symbol.

    If the given bone_name is not sided, then this function returns None.
    """

    # This is a string if the bone_name ends with a numeric suffix like '.001'.
    # Otherwise, it is an empty string.
    bone_name_numeric_suffix = get_name_numeric_suffix(bone_name)

    # This is always an integer 0 or greater.
    bone_name_numeric_suffix_length = len(bone_name_numeric_suffix)

    # The bone_name_stem is the bone_name, stripped of any numeric suffix if
    # there is any.
    bone_name_stem = (
        bone_name[:-bone_name_numeric_suffix_length]
        if bone_name_numeric_suffix
        else bone_name
    )

    (bone_side, opposite_bone_name_stem, bilateral_bone_name_stem) = (
        parse_bone_name_stem(bone_name_stem)
    )

    # If a bone_side was assigned by any of the previous branches, then there
    # was a match for a sided bone_name, and this function returns the tuple
    # result.
    if bone_side:
        opposite_bone_name = (
            opposite_bone_name_stem + bone_name_numeric_suffix
        )
        bilateral_bone_name = (
            bilateral_bone_name_stem + bone_name_numeric_suffix
        )
        return (bone_side, opposite_bone_name, bilateral_bone_name)

    # Otherwise, this function returns None.


def symmetrically_match_bone_names(bone_name_0, bone_name_1):
    """
    This function checks whether the two given bone names match across
    symmetry. Either they must be the same unsided bone name or they must be
    opposite-sided bone names.
    """

    # This is None when bone_0 is not sided.
    bone_name_parse_result_0 = parse_sided_bone_name(bone_name_0)

    if bone_name_0 == bone_name_1:
        # Because the two bone names are equal, whether they are considered to
        # be symmetrically matching depends on whether they are sided.
        return bone_name_parse_result_0 is None

    # In this case, because the two bone names are unequal…
    bone_name_parse_result_1 = parse_sided_bone_name(bone_name_1)

    # …then the bone names must both be sided…
    either_bone_name_is_unsided = (
        bone_name_parse_result_0 is None
        or bone_name_parse_result_1 is None
    )
    if either_bone_name_is_unsided:
        return False

    # …they must have opposite sides…
    bone_side_0, opposite_bone_name_0, _ = bone_name_parse_result_0

    bone_side_1, opposite_bone_name_1, _ = bone_name_parse_result_1

    bone_sides_are_opposite = (
        (bone_side_0 == 'left' and bone_side_1 == 'right')
        or
        (bone_side_0 == 'right' and bone_side_1 == 'left')
    )

    if not bone_sides_are_opposite:
        return False

    # …and they must be the paired opposite-sided version of one another (as
    # if the Symmetrize operation were performed on either of them)…
    bone_names_are_opposite = (
        (bone_name_0 == opposite_bone_name_1)
        and
        (opposite_bone_name_0 == bone_name_1)
    )

    if not bone_names_are_opposite:
        return False

    # …in order for them to be considered matching.
    return True


def match_bone_parents(bone_0, bone_1):
    """
    This function checks whether the two given Bones have matching parent
    Bones.

    If both Bones do not have a parent, then this function returns True.

    If the two Bones have an equal parent – and if that parent is not sided –
    then this function returns True.

    If the two Bones have unequal parents – and if each of those parents is the
    opposite-sided version of the other – then this function returns True.

    Otherwise, this function returns False.
    """
    parent_bone_0 = bone_0.parent
    parent_bone_1 = bone_1.parent

    # If either parent bone is None, then we only have to check whether the
    # other parent bone is None.
    if parent_bone_0 is None:
        return parent_bone_1 is None
    elif parent_bone_1 is None:
        return parent_bone_0 is None

    parent_bone_name_0 = parent_bone_0.name
    parent_bone_name_1 = parent_bone_1.name

    return symmetrically_match_bone_names(
        parent_bone_name_0, parent_bone_name_1,
    )


def match_opposite_constraints(
    bone_constraint_0,
    bone_constraint_1,
    armature_object,
):
    """
    This function checks whether the two given constraints are opposite
    versions of one another.

    The armature_object scene object is used to check whether constraints are
    targeting other, external scene objects rather than within the same
    armature scene object (in which case the constraints’ subtargets are not
    symmetrized, as per Blender’s bone Symmetrize behavior).
    """
    # First check if they have matching types.
    if bone_constraint_0.type != bone_constraint_1.type:
        return False

    # Next check if they have target scene objects.
    # Not all constraints have target attributes – e.g., Limit Rotation.
    target_0 = getattr(bone_constraint_0, 'target', None)
    target_1 = getattr(bone_constraint_1, 'target', None)
    if target_0 is not target_1:
        return False

    # Next check whether the constraints’ subtargets match. Subtargets are
    # bone- name strings. (Not all constraints have subtarget attributes –
    # e.g., Limit Rotation.)
    subtarget_name_0 = getattr(bone_constraint_0, 'subtarget', None)
    subtarget_name_1 = getattr(bone_constraint_1, 'subtarget', None)

    # If the constraints’ target is an outside scene object, rather than the
    # same armature scene object that owns the constraints’ bones, then
    # subtargets are not expected to switch to their opposite sides, as per
    # Blender’s bone Symmetrize behavior.
    if target_0 is not armature_object:
        return subtarget_name_0 == subtarget_name_1

    # Otherwise, if the constraints are targeting the same armature scene
    # object that owns their bones, then their subtargets are expected to be
    # opposite of one another.

    return symmetrically_match_bone_names(subtarget_name_0, subtarget_name_1)


def match_bone_constraints(bone_0, bone_1, armature_object):
    """
    This function checks whether the two given Bones bone_0 and bone_1, both
    owned by armature_object.data, have matching constraint collections. Two
    constraint collections are considered to match if they have the same length
    and if:

    For each index integer in the constraint collections, the corresponding
    constraints from both collections have the same name, the same type, the
    same target, and mutually opposite-sided subtarget bone names.

    When two constraints both target another, external scene object rather than
    bones within the same armature scene object, then those constraint’s
    subtargets are not symmetrized, as per Blender’s bone Symmetrize behavior.
    In this case, the subtargets must be identical.

    When two constraints do target their bones’ owner armature scene object,
    their subtarget bone names are considered to match only if both of them are
    blank (both no target), if both of them are the same non-sided bone name
    (neither left- nor right-sided), or if they are opposite-sided bones (the
    same name but symmetrized).
    """
    pose = armature_object.pose
    bone_constraint_collection_0 = pose.bones[bone_0.name].constraints
    bone_constraint_collection_1 = pose.bones[bone_1.name].constraints

    num_of_constraints = len(bone_constraint_collection_0)
    if num_of_constraints != len(bone_constraint_collection_1):
        return False

    for bone_constraint_index in range(0, num_of_constraints):
        bone_constraint_0 = bone_constraint_collection_0[bone_constraint_index]
        bone_constraint_1 = bone_constraint_collection_1[bone_constraint_index]

        if not match_opposite_constraints(
            bone_constraint_0,
            bone_constraint_1,
            armature_object,
        ):
            return False

    return True


def classify_bone(bone, armature_object):
    """
    This function classifies the given Bone bone from the given armature_object
    into one of the following “bone-type” strings:

    'asymmetric': These are bones do not have any paired opposite-sided bone.

    'left_symmetric': These are left-sided bones that each has exactly one
    paired right-sided bone, which in turn must share the same relationship
    names, types, targets, and parameters.

    'right_symmetric': These are right-sided bones that each has exactly one
    paired left-sided bone, which in turn must share the same relationship
    names, types, targets, and parameters.

    'antisymmetric': These are left- or right-sided bones that either do not
    have a paired opposite-sided bone or do not completely match their paired
    opposite-sided bone (e.g., if their parents do not match or if either of
    them have a constraint that is missing or different in the other bone).
    The match_bone_parents and match_bone_constraints functions are used here.

    The armature_object must be the armature scene object that owns the Bone.

    The function returns a tuple: (bone_type, opposite_bone_name,
    bilateral_bone_name). opposite_bone_name and bilateral_bone_name are both
    None if the bone type is 'asymmetric'.

    Most armatures will have only one opposite-sided bone that matches each
    left- or right-sided bone. However, there are edge cases when multiple
    left- or right-sided bone names differ only in case (e.g., with bones named
    “Example LeFT”, “Example Left”, “Example RiGHT”, and “Example Right”, the
    Symmetrize operation’s results depend on which bone(s) is selected and the
    armature’s internal bone order). Blender’s bone Symmetrize operation may
    behave quirkly in such cases. Therefore, for simplicity, this function
    checks for paired opposite-sided bones on an individual bone basis, as if
    each bone were individually selected before using the Symmetrize operation.
    In the preceding example, both “Example LeFT” and “Example Left” would
    correspond to “Example Right”, and both “Example RiGHT” and “Example Right”
    correspond to “Example Left”. It is these pairs that are checked for
    equivalence.
    """
    bone_name = bone.name
    bone_name_parse_result = parse_sided_bone_name(bone_name)
    bone_collection = armature_object.data.bones
    pose_bone_collection = armature_object.pose.bones

    if bone_name_parse_result:
        # In this case, the Bone is either left- or right-sided.
        bone_side, opposite_bone_name, bilateral_bone_name = (
            bone_name_parse_result
        )
        if opposite_bone_name in bone_collection:
            # In this case, the Bone indeed has a paired opposite-sided
            # PoseBone, so it might be symmetrical. We must compare their
            # parents and their PoseBones’ constraints for equivalence.
            opposite_bone = bone_collection[opposite_bone_name]
            pose_bone = pose_bone_collection[bone_name]
            opposite_pose_bone = pose_bone_collection[opposite_bone_name]
            bone_and_opposite_bone_match = (
                match_bone_parents(bone, opposite_bone)
                and match_bone_constraints(
                    pose_bone,
                    opposite_pose_bone,
                    armature_object=armature_object,
                )
            )

            if bone_and_opposite_bone_match:
                if bone_side == 'left':
                    return (
                        'left_symmetric',
                        opposite_bone_name,
                        bilateral_bone_name,
                    )
                else:
                    return (
                        'right_symmetric',
                        opposite_bone_name,
                        bilateral_bone_name,
                    )
            else:
                # In this case, the PoseBone and its paired opposite-sided
                # PoseBone do not have matching parent PoseBones; the PoseBone
                # is therefore antisymmetric.
                return (
                    'antisymmetric',
                    opposite_bone_name,
                    bilateral_bone_name,
                )
        else:
            # In this case, the PoseBone has no paired opposite-sided PoseBone,
            # and the PoseBone is therefore antisymmetric.
            return ('antisymmetric', opposite_bone_name, bilateral_bone_name)
    else:
        # In this case, because the PoseBone’s name is neither left- or
        # right-sided, it is asymmetric (but not antisymmetric).
        return ('asymmetric', None, None)


def is_bone_hide_set_to_true_in_mode(bone, armature_object, context_mode):
    """
    Check if the bone itself is set to be hidden. The bone must be a Bone
    struct (not an EditBone or a PoseBone).

    Bones actually have two visibility states: one for Object and Pose Modes,
    in bone.hide – and a separate one for Edit Mode, in its corresponding
    EditBone’s hide attribute.
    """
    if context_mode == 'EDIT_ARMATURE':
        return armature_object.data.edit_bones[bone.name].hide
    else:
        return bone.hide

def is_bone_invisible_without_symmetry(bone, armature_object, context_mode):
    """
    A helper function for is_bone_invisible. The bone must be a Bone struct
    (not an EditBone or a PoseBone).
    """

    if is_bone_hide_set_to_true_in_mode(bone, armature_object, context_mode):
        return True

    # Check whether any of the armature’s visible bone groups has the bone.
    # Each of these variables is an array of 32 booleans – one for each of the
    # 32 bone layers of the armature.
    bone_layer_visibility_list = armature_object.data.layers
    bone_layer_membership_list = bone.layers
    visibilities_due_to_bone_layers_list = [
        bone_layer_visibility and bone_layer_membership
        for bone_layer_visibility, bone_layer_membership
        in zip(bone_layer_visibility_list, bone_layer_membership_list)
    ]

    return not any(visibilities_due_to_bone_layers_list)


def are_bone_and_opposite_invisible(bone, armature_object, context_mode):
    """
    This function is a predicate function with one parameter. It returns True,
    unless the following conditions are true (in which case it returns False):

    * Its argument is a Bone struct.
    * Not a single one of its armature’s visible bone groups contains the bone
      – or if the bone is itself set to be hidden in the current context_mode.
    * The bone is not symmetric (as defined by the analyzebones module’s
      classify_bone function) – or, if it is symmetric, its opposite-sided bone
      is not invisible.
    """

    if not is_bone_invisible_without_symmetry(
        bone=bone,
        armature_object=armature_object,
        context_mode=context_mode,
    ):
        # In this case, the given bone itself is visible.
        return False

    # In this case, the given bone itself is invisible. Check whether its
    # opposite-sided bone (if it is symmetric with it) is also invisible.
    (bone_type, opposite_bone_name, _) = classify_bone(bone, armature_object)
    if bone_type != 'left_symmetric' and bone_type != 'right_symmetric':
        # In this case, both the given bone itself is invisible, and it is not
        # symmetric with any other bone. (It is either antisymmetric with
        # another bone or it is asymmetric.)
        return True

    # In this case, the given bone itself is invisible, but it is symmetric
    # with its opposite-sided bone. Use is_bone_invisible_without_symmetry
    # again – but this time on the opposite-sided bone.
    opposite_bone = armature_object.data.bones.get(opposite_bone_name)
    return is_bone_invisible_without_symmetry(
        bone=opposite_bone,
        armature_object=armature_object,
        context_mode=context_mode,
    )


def normalize_symmetric_bones_to_left_side(bones, armature_object):
    """
    This function returns a list of the given bones, except that right-sided
    symmetric bones are replaced by their opposite-sided version from the given
    armature_object.
    """

    def normalize_bone(b):
        (bone_type, opposite_bone_name, _) = classify_bone(b, armature_object)
        if bone_type == 'right_symmetric':
            # Convert right-sided bones to their opposite-sided versions.
            return armature_object.data.bones[opposite_bone_name]
        else:
            # Other bones stay the same.
            return b

    return [normalize_bone(b) for b in bones]
