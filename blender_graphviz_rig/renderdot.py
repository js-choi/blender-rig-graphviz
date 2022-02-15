# This module is licensed by its authors under the GNU Affero General Public
# License 3.0.

"""
This module is a lightweight DOT renderer. It takes information representing a
directed graph in the DOT language, and it transforms the data into a text
document in the DOT language.

It supports a limited subset of DOT: all nodes must belong to a cluster (i.e.,
a subgraph). “Entities” are either clusters (i.e., subgroups), nodes, or edges.

We define the following named arguments as such –

free_nodes: A set of node IDs that do not belong to any cluster.

cluster_nodes_dict: A dictionary from each cluster ID to a set of the node IDs
that the cluster contains.

edge_tuple_dict: A dictionary from each edge ID to its tuple pair
(source_node_id, destination_node_id).

entity_label_dict: A dictionary from each entity ID to its label, if any.

entity_categories_dict: A dictionary from each entity ID to a tuple of category
names. (“Entity categories” are a lightweight way to apply recurring DOT
attributes to various entities.)

category_attrs_dict: A dictionary from each category name to an attribute
dictionary. The attribute dictionary in turn is from DOT attribute key strings
to attribute value strings.

For example, this:

.. code-block: python
    print(create_dot_digraph(
        cluster_nodes_dict={0: (2, 3), 1: ((4, 5))},
        edge_tuple_dict={6: (3, 2), 7: (5, 4), 8: (5, 3)},
        entity_label_dict={
            0: 'A', 1: 'B', 2: 'A0', 3: 'A1', 4: 'B0', 5: 'B1',
            6: 'E0', 7: 'E1', 8: 'E2',
        },
        entity_categories_dict={2: (100,), 3: (101,), 8: (102,)},

        category_attrs_dict={
            100: {
                'shape': 'box',
                'fillcolor': 'gray40',
                'style': 'rounded, filled',
            ],
            101: {
                'fillcolor': 'gray85',
                'style': 'rounded, filled, bold',
            },
            102: {
                'color': 'gray50',
                'fontcolor': 'gray25',
                'arrowsize': 0.5,
            },
        },
        fontname='Gill Sans',
    ))

…returns DOT text that resembles this string (without line breaks or indents):

.. code-block: dot
    digraph {
      graph [style=rounded color=gray75 fontname="Gill Sans" fontsize=24];
      node [shape=plaintext style=rounded fontname="Gill Sans"];
      edge [fontsize=10 fontname="Gill Sans"];
      subgraph "cluster_0" {
        label="A";
        "2" [label="A0"; "shape": "box", "fillcolor"="gray40",
          "style"="rounded, filled"];
        "3" [label="A1", "fillcolor"="gray85",
          "style"="rounded, filled, bold"];
      }
      subgraph "cluster_1" {
        label="B";
        "4" [label="B0", "shape": "box", "fillcolor"="gray40",
          "style"="rounded, filled", "fillcolor"="gray85",
          "style"="rounded, filled, bold"];
        "5" [label="B1"];
      }
      "3" -> "2" [label="E0"];
      "5" -> "4" [label="E1"];
      "5" -> "3" [label="E2", "color"="gray50", "fontcolor"="gray25",
        "arrowsize"="0.5"]; }
"""

escape_translation_table = {
    # ASCII quotation marks are backslashed.
    '"': '\\"',
    # Backslashes are also backslashed.
    '\\': '\\\\',
}


def escape_quotes(input):
    """
    This function gets the string version of input then escapes any ASCII
    quotation marks " or backslashes \\ in the string with backslashes.
    """
    return str(input).translate(escape_translation_table)


def create_dot_attr_list(
    entity_id,
    entity_label_dict={},
    entity_categories_dict={},
    category_attrs_dict={},
):
    """
    This function renders the DOT attribute list for the given entity_id,
    including the entity’s label and the attrs given by its entity categories.
    The string starts with one space character.

    Named parameters are described in the module docstring.
    """
    label = entity_label_dict.get(entity_id)
    entity_categories = entity_categories_dict.get(entity_id, [])

    attr_string_list = [
        # First attribute is the label, if any.
        *(
            [f'label="{escape_quotes(label)}"']
            if label
            else []
        ),
        # Then the attrs given by the entity’s categories (if any).
        *[
            f'"{escape_quotes(attr_key)}"="{escape_quotes(attr_val)}"'
            for category_name
            in entity_categories
            for attr_key, attr_val
            in category_attrs_dict.get(category_name, {}).items()
        ],
    ]
    return (
        ' ['
        + ', '.join(attr_string_list)
        + ']'
        if len(attr_string_list)
        else ''
    )


def create_dot_node(
    node_id,
    entity_label_dict={},
    entity_categories_dict={},
    category_attrs_dict={},
):
    """
    This function renders a DOT node statement, with its label and other
    attrs.

    Named parameters are described in the module docstring.
    """
    return (
        # This is a single node statement. It starts with the node ID.
        f'"{escape_quotes(node_id)}"'
        # Then the node attribute list.
        + create_dot_attr_list(
            node_id,
            entity_label_dict=entity_label_dict,
            entity_categories_dict=entity_categories_dict,
            category_attrs_dict=category_attrs_dict,
        )
        # Close the node statement.
        + ';'
    )


def create_dot_cluster(
    cluster_id,
    cluster_nodes_dict={},
    entity_label_dict={},
    entity_categories_dict={},
    category_attrs_dict={},
):
    """
    This function renders a DOT cluster statement, with its label and a series
    of statements for its contained nodes. (Node statements only declare their
    existence; they do not include any attrs.)

    Named parameters are described in the module docstring.
    """
    return (
        # Start the cluster statement.
        f'subgraph "cluster_{escape_quotes(cluster_id)}" '
        '{ '
        # The cluster label needs to use a large font.
        f'fontsize=24; '
        # Declare the cluster label.
        f'label="{entity_label_dict.get(cluster_id, "")}"; '
        # Child node statements.
        + ' '.join([
            create_dot_node(
                node_id,
                entity_label_dict=entity_label_dict,
                entity_categories_dict=entity_categories_dict,
                category_attrs_dict=category_attrs_dict,
            )
            for node_id
            in cluster_nodes_dict.get(cluster_id)
        ])
        # Close the cluster statement.
        + ' }'
    )


def create_dot_edge(
    edge_id,
    source_id,
    destination_id,
    entity_label_dict={},
    entity_categories_dict={},
    category_attrs_dict={},
):
    """
    This function renders a DOT edge statement, with its label and other
    attrs.

    Named parameters are described in the module docstring.
    """
    return (
        # This is a single edge statement. It starts with the edge source.
        f'"{escape_quotes(source_id)}" '
        # Then the edge destination.
        f'-> "{escape_quotes(destination_id)}"'
        # Then the edge attribute list.
        + create_dot_attr_list(
            edge_id,
            entity_label_dict=entity_label_dict,
            entity_categories_dict=entity_categories_dict,
            category_attrs_dict=category_attrs_dict,
        )
        # Close the edge statement.
        + ';'
    )


def create_dot_digraph(
    free_nodes=set(),
    cluster_nodes_dict={},
    edge_tuple_dict={},
    entity_label_dict={},
    entity_categories_dict={},
    category_attrs_dict={},
    title='',
    fontname='',
    rankdir='',
):
    """
    This function takes information representing a directed graph, and it
    transforms the data into a text document in the DOT language. It returns a
    string.

    The title string, if given, is displayed in small text at the bottom.

    The fontname is supplied as a graph attribute to Graphviz.

    The rankdir is also supplied as a graph attribute to Graphviz; it
    determines the direction in which increasing node rank goes: 'TB' (top to
    bottom, which is Graphviz’s default) or 'LR' (left to right, which the
    legend uses).

    Named parameters are described in the module docstring.
    """
    return (
        # With Graphviz, the default fontsize is 10.
        'digraph { '
        # Default graph attributes.
        'graph ['
        f'rankdir="{escape_quotes(rankdir)}" '
        'style=rounded '
        'color=gray75 '
        f'fontname="{escape_quotes(fontname)}" '
        # This font size will be used for the small title of the graph.
        'fontsize=10'
        ']; '
        # Default node attributes.
        f'node [shape=plaintext style=rounded fontname="{fontname}"]; '
        # Default edge attributes.
        f'edge [fontsize=10 fontname="{fontname}"]; '
        # The title of the graph, if any.
        f'label="{escape_quotes(title)}"; '

        # The bulk of the graph data.
        + ' '.join([
            # Free-node statements, with their labels and other attrs.
            *[
                create_dot_node(
                    node_id,
                    entity_label_dict=entity_label_dict,
                    entity_categories_dict=entity_categories_dict,
                    category_attrs_dict=category_attrs_dict,
                )
                for node_id
                in free_nodes
            ],

            # Cluster statements, with their labels and contained nodes.
            *[
                create_dot_cluster(
                    cluster_id,
                    entity_label_dict=entity_label_dict,
                    cluster_nodes_dict=cluster_nodes_dict,
                    entity_categories_dict=entity_categories_dict,
                    category_attrs_dict=category_attrs_dict,
                )
                for cluster_id
                in cluster_nodes_dict
            ],

            # Edge statements, with their labels and other attrs.
            *[
                create_dot_edge(
                    edge_id,
                    source_id,
                    destination_id,
                    entity_label_dict=entity_label_dict,
                    entity_categories_dict=entity_categories_dict,
                    category_attrs_dict=category_attrs_dict,
                )
                for edge_id, (source_id, destination_id)
                in edge_tuple_dict.items()
            ],
        ])
        # Close the entire digraph.
        + ' }'
    )
