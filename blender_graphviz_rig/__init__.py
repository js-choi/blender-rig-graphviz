# This module is licensed by its authors under the GNU Affero General Public
# License 3.0.

"""
This Blender add-on can render graph images depicting the parent and constraint
relationships between scene objects (and their bones).

The add-on requires the `Graphviz`_ application to be installed and available
from the OS’s shell.

Operator classes’ names follow the `standard class-registration conventions`_.

.. _DOT language: https://www.graphviz.org/doc/info/lang.html
.. _Graphviz: https://www.graphviz.org/
.. _standard class-registration conventions: https://wiki.blender.org/wiki/Reference/Release_Notes/2.80/Python_API/Addons#Class_Registration
""" # noqa

from .analyzerigs import analyze_rig_graph, create_legend_data
from .analyzebones import (
    are_bone_and_opposite_invisible,
    normalize_symmetric_bones_to_left_side,
)
from .renderdot import create_dot_digraph
from .savefiles import save_files, GraphvizNotFoundError, GraphvizOutputError

from datetime import datetime
import os
import errno
import sys

import bpy

bl_info = {
    'name': 'Rig Graphviz',
    'version': (1, 0, 0),
    'blender': (3, 0, 0),
    'category': 'Rigging',
    'support': 'COMMUNITY',
    'description': (
        'Creates a Graphviz graph description for the selected objects’ '
        'parent and constraint relationships.'
    ),
    'location': (
        'View3D → Object → Rig Graphviz, '
        'View3D → Armature → Rig Graphviz, or '
        'View3D → Pose → Rig Graphviz'
    ),
    'doc_url': (
        'https://github.com/js-choi/blender-rig-graphviz/'
        'blob/main/README.rst'
    ),
    'tracker_url': (
        'https://github.com/js-choi/blender-armature-graphviz/'
        'tree/main/CONTRIBUTING.rst'
    ),
}

active_object_filename_marker = '{{active_object_name}}'


def get_default_dot_command():
    """
    The default DOT command depends on the OS.
    In Linux and macOS, the DOT application is assumed to be available from the
    shell path: 'dot'. But in Windows, Graphviz’s installer might not
    necessarily add 'dot' to the system path, so we directly point to its
    default absolute file location: 'C:\\Program Files\\Graphviz\bin\\dot'.
    """
    if sys.platform == 'win32':
        return r'C:\Program Files\Graphviz\bin\dot'
    else:
        return 'dot'


def get_default_fontname():
    """
    Returns a string. The default font depends on the OS. If the current OS has
    no default font, then this returns a blank string.
    """
    if sys.platform == 'linux':
        return 'Nimbus Sans L'
    elif sys.platform == 'darwin':
        return 'Gill Sans'
    elif sys.platform == 'win32':
        return 'Calibri'
    else:
        return ''


class ArmatureGraphvizAddonPreferences(bpy.types.AddonPreferences):
    """
    This class defines the add-on’s preferences.
    """

    # This attribute is used by Blender. It must match the package name.
    bl_idname = __package__

    dot_command: bpy.props.StringProperty(
        name='Graphviz DOT Command',
        subtype='FILE_PATH',
        default=get_default_dot_command(),
    )

    output_fontname: bpy.props.StringProperty(
        name='Font Name',
        default=get_default_fontname(),
    )

    output_directory_path: bpy.props.StringProperty(
        name='Output Directory',
        subtype='FILE_PATH',
        # If the configured output directory starts with '//', then the '//' is
        # replaced by a path to the current Blender file’s directory.
        default='//',
    )

    output_filename: bpy.props.StringProperty(
        name='Output Filename',
        default=f'Rig Graphviz {active_object_filename_marker}',
    )

    def draw(self, context):
        """
        Blender calls this method when drawing the preference pane.
        """
        layout = self.layout
        layout.prop(self, 'dot_command')
        layout.label(
            text=(
                'The shell command to run the Graphviz DOT application. '
                'See https://www.graphviz.org/download/.'
            ),
        )
        layout.prop(self, 'output_fontname')
        layout.label(
            text=(
                'A system font by this name must be visible to Graphviz. '
                'If blank, Graphviz will use an OS-dependent default font.'
            ),
        )
        layout.prop(self, 'output_directory_path')
        layout.label(
            text=(
                'If the output directory path starts with //, '
                'then the // will be replaced '
                'by the current Blender file’s directory path.'
            ),
        )
        layout.prop(self, 'output_filename')
        layout.label(
            text=(
              'Any {{active_object_name}} string in the filename '
              'will be replaced by the active object’s name.'
            ),
        )
        layout.label(
            text=(
              'A “.png” file extension will also be automatically appended '
              'to the filename.'
            ),
        )


# This dictionary maps “entity categories” (for clusters, nodes, and edges) to
# dictionaries of DOT styles. See the renderdot module’s docstring for more
# information.
dot_category_attrs_dict = {
    'deforming': {
        'fillcolor': 'gray90',
        'style': 'rounded, filled',
    },
    'antisymmetric': {
        'fillcolor': 'lightcoral',
        'style': 'rounded, filled',
    },
    'root': {
        'shape': 'circle',
    },
    'constraint': {
        'color': 'gray50',
        'fontcolor': 'gray50',
        'arrowsize': '0.5',
    },
    # Invisible edges group the nodes in the legend into rows and columns.
    'invisible': {
        'style': 'invisible',
        'arrowhead': 'none',
    },
}


def get_rig_output_filename(context):
    """
    When rendering a rig Graphviz image, this function gets the output
    filename. This function is not used when rendering a Graphviz image with a
    static filename – i.e., a legend.
    """
    # This is a LayerObjects structure. It is guaranteed to have one active
    # object, though it may have zero selected object.
    view_layer_object_collection = context.view_layer.objects
    active_object = view_layer_object_collection.active

    addon_preferences = context.preferences.addons[__package__].preferences

    return addon_preferences.output_filename.replace(
        active_object_filename_marker,
        active_object.name,
    )


def run_rig_graphviz_operator(
    self,
    context,
    graph_data,
    output_filename,
    create_success_message,
    title='',
    rankdir='',
):
    """
    With the given Blender operator (self), this function renders a Graphviz
    image from the given operands in the given Blender context. When
    successfully finished, either the singular_operand_word or
    plural_operand_word is used to create a message to the user.

    The rankdir argument is passed to create_dot_digraph in the renderdot
    module; see its docstring for more information.
    """
    addon_preferences = context.preferences.addons[__package__].preferences

    preferences_output_directory_path = addon_preferences.output_directory_path

    # If the add-on preferences’ output directory starts with '//', then the
    # '//' is replaced by a path to the current Blender file’s directory using
    # bpy.path.abspath.
    resolved_output_directory_path = (
        bpy.path.abspath(preferences_output_directory_path)
    )

    # If the resolved_output_directory_path is '', and if the
    # preferences_output_directory_path is the default '//', then that means
    # the Blender file is a new and unsaved file (so it has no containing
    # directory). It is easy for users to encounter this problem, so we have a
    # special error message devoted to it.
    attempted_to_save_to_nonexistent_current_directory = (
        resolved_output_directory_path == ''
        and preferences_output_directory_path == '//'
    )
    if (attempted_to_save_to_nonexistent_current_directory):
        self.report({'ERROR'}, (
            'This Blender file has not yet been saved, '
            'so there is no current directory in which to save images. '
            'Save this Blender file, or specify an output directory '
            'in the Rig Graphviz add-on’s preferences.'
        ))
        return {'CANCELLED'}

    dot_command = addon_preferences.dot_command

    output_fontname = addon_preferences.output_fontname

    output_file_path = (
        os.path.join(resolved_output_directory_path, output_filename)
        + '.png'
    )

    dot_source_file_path = (
        os.path.join(bpy.app.tempdir, output_filename)
    )

    dot_text = create_dot_digraph(
        **graph_data,
        category_attrs_dict=dot_category_attrs_dict,
        title=title,
        fontname=output_fontname,
        rankdir=rankdir,
    )

    # Try to render and save the image file. Report and return an error status
    # to Blender if rendering/saving fails.
    try:
        save_files(
            dot_text=dot_text,
            dot_command=dot_command,
            dot_source_file_path=dot_source_file_path,
            output_directory_path=resolved_output_directory_path,
            output_filename=output_filename,
        )

    except GraphvizNotFoundError:
        # In this case, Graphviz has not been installed on the OS, so its
        # executable applications are not available in the system shell.
        self.report({'ERROR'}, (
            'Failed to create image. '
            'Graphviz has not been installed '
            'or is not available from the system shell '
            f'with the “{dot_command}” command. '
            'See the Rig Graphviz add-on’s DOT-command preference.'
        ))
        return {'CANCELLED'}

    except GraphvizOutputError as err:
        # In this case, Graphviz itself reported an unexpected error, such as
        # a syntax error in the generated DOT file.
        self.report({'ERROR'}, (
            f'Failed to create image at “{output_file_path}”. '
            f'Graphviz reported the following error – {err}'
        ))
        return {'CANCELLED'}

    except OSError as err:
        # In this case, a strange and unexpected error from the OS occurred.
        self.report({'ERROR'}, (
            f'Failed to create image at “{output_file_path}”. '
            f'The OS reported the following error – {err}'
        ))
        return {'CANCELLED'}

    # Load the image file into the Blender file as an external Image
    # data-block, replacing any existing Image data-block whose name is the
    # same as the filename.
    image_data_block = bpy.data.images.load(
        output_file_path,
        check_existing=True,
    )

    # Reload the image data-block so that, if it is being already displayed
    # somewhere in the UI, the UI will refresh the image’s view.
    image_data_block.reload()

    # Save the image data-block even though it has no users, protecting it from
    # data-block purging from the Blender file.
    image_data_block.use_fake_user = True

    # Show a message to the user when finished.
    self.report({'INFO'}, create_success_message(output_file_path))

    return {'FINISHED'}


def create_time_description():
    """
    Creates a terse, human-readable timestamp string for the current datetime.
    """
    time_format = '%Y-%m-%d %H:%M UTC'
    now = datetime.now()
    return now.strftime(time_format)


def pluralize_object(num):
    return 'object' if num == 1 else 'objects'


def pluralize_bone(num):
    return 'bone' if num == 1 else 'bones'


def create_object_render_success_message(
    output_file_path,
    operands,
    bone_determiner_word,
):
    """
    This creates a message string for successful rendering of a rig graph over
    object operands. The bone_determiner_word is either 'all' or 'visible'.
    """
    num_of_operands = len(operands)
    operands_word = pluralize_object(num_of_operands)
    return (
        f'Graphviz diagram for {num_of_operands} {operands_word} '
        f'with {bone_determiner_word} bones '
        f'has been rendered to “{output_file_path}” '
        'and added to this file as an image data-block.'
    )


def create_bone_render_success_message(output_file_path, operands):
    num_of_operands = len(operands)
    operands_word = pluralize_bone(num_of_operands)
    return (
        f'Graphviz diagram for {num_of_operands} {operands_word} '
        f'has been rendered to “{output_file_path}” '
        'and added to this file as an image data-block.'
    )


def create_legend_render_success_message(output_file_path):
    return (
        f'Graphviz rig legend '
        f'has been rendered to “{output_file_path}” '
        'and added to this file as an image data-block.'
    )


class OBJECT_OT_rig_graphviz_with_all_bones(bpy.types.Operator):
    # The docstring is used by Blender for its description, so we do not use
    # line breaks. A period is also automatically added by Blender.
    'Render an image of relationships between active/selected scene objects (and all of their bones)' # noqa

    # This attribute is used by Blender as the operator’s Python ID.
    bl_idname = 'object.rig_graphviz_with_all_bones'
    # This attribute is used by Blender as the operator’s menu label.
    bl_label = 'Render Graph with All Bones'

    def execute(self, context):
        """
        Blender calls this method when the operator is activated. It will
        start the operator’s action and continue it as a running modal with
        regular timer events (see the modal method).
        """
        # This is a LayerObjects structure. It is guaranteed to have one active
        # object, though it may have zero selected object.
        view_layer_object_collection = context.view_layer.objects
        active_object = view_layer_object_collection.active
        selected_objects = view_layer_object_collection.selected

        # Include both the active object and selected objects.
        operands = set([active_object, *selected_objects])

        # All operand scene objects must be updated with any pending edit-mode
        # data. See <https://blender.stackexchange.com/q/139101>. (This must be
        # done before accessing any actual data-blocks. See
        # <https://developer.blender.org/T53135#467105>.)
        for so in operands:
            so.update_from_editmode()

        graph_data = analyze_rig_graph(
            operands,
            # No bones are excluded by the command (although right-sided
            # symmetric bones are still excluded, since they are redundant with
            # left-sided bones).
            is_bone_excluded=lambda bone, armature_object:
                False,
        )

        time_string = create_time_description()
        num_of_operands = len(operands)
        object_word = pluralize_object(num_of_operands).capitalize()
        title = (
            f'{time_string} • {num_of_operands} {object_word} '
            'with All Bones'
        )

        return run_rig_graphviz_operator(
            self,
            context=context,
            graph_data=graph_data,
            output_filename=get_rig_output_filename(context),
            create_success_message=lambda output_file_path:
                create_object_render_success_message(
                    output_file_path,
                    operands,
                    bone_determiner_word='all',
                ),
            title=title,
        )


class OBJECT_OT_rig_graphviz_with_visible_bones(bpy.types.Operator):
    # The docstring is used by Blender for its description, so we do not use
    # line breaks. A period is also automatically added by Blender.
    'Render an image of relationships between active/selected scene objects (and their visible bones)' # noqa

    # This attribute is used by Blender as the operator’s Python ID.
    bl_idname = 'object.rig_graphviz_with_visible_bones'
    # This attribute is used by Blender as the operator’s menu label.
    bl_label = 'Render Graph with Visible Bones'

    def execute(self, context):
        """
        Blender calls this method when the operator is activated. It will
        start the operator’s action and continue it as a running modal with
        regular timer events (see the modal method).
        """
        # This is a LayerObjects structure. It is guaranteed to have one active
        # object, though it may have zero selected object.
        view_layer_object_collection = context.view_layer.objects
        active_object = view_layer_object_collection.active
        selected_object_list = list(view_layer_object_collection.selected)

        # If no objects are selected, then use the active object.
        operands = selected_object_list or [active_object]

        # All operand scene objects must be updated with any pending edit-mode
        # data. See <https://blender.stackexchange.com/q/139101>. (This must be
        # done before accessing any actual data-blocks. See
        # <https://developer.blender.org/T53135#467105>.)
        for so in operands:
            so.update_from_editmode()

        graph_data = analyze_rig_graph(
            operands,
            is_bone_excluded=lambda bone, armature_object:
                are_bone_and_opposite_invisible(
                    bone=bone,
                    armature_object=armature_object,
                    context_mode=context.mode,
                ),
        )

        time_string = create_time_description()
        num_of_operands = len(operands)
        object_word = pluralize_object(num_of_operands).capitalize()
        title = (
            f'{time_string} • {num_of_operands} {object_word} '
            'with Visible Bones'
        )

        return run_rig_graphviz_operator(
            self,
            context=context,
            graph_data=graph_data,
            output_filename=get_rig_output_filename(context),
            create_success_message=lambda output_file_path:
                create_object_render_success_message(
                    output_file_path,
                    operands,
                    bone_determiner_word='visible',
                ),
            title=title,
        )

    def invoke(self, context, event):
        """
        Blender calls this method when the operator is activated by a UI event
        (e.g., by using one of its menu items).
        """
        # There is no extra information needed from the event, so we need to
        # do nothing extra before delegating to the execute method.
        return self.execute(context)


def get_selected_bones(context):
    """
    Returns a list of the selected Bone structs for the currently selected
    EditBones (if in armature Edit Mode) or for the currently selected
    PoseBones (if in Pose Mode).
    """
    # This is an armature scene object.
    active_object = context.view_layer.objects.active

    # The armature scene object must be updated with any pending edit-mode
    # data. See <https://blender.stackexchange.com/q/139101>. (This must be
    # done before accessing any actual data-blocks. See
    # <https://developer.blender.org/T53135#467105>.)
    active_object.update_from_editmode()

    if context.mode == 'EDIT_ARMATURE':
        return [
            active_object.data.bones[eb.name]
            for eb
            in context.selected_bones
        ]

    elif context.mode == 'POSE':
        return [
            active_object.data.bones[pb.name]
            for pb
            in context.selected_pose_bones
        ]


class ARMATURE_OT_rig_graphviz_selected_bones_only(bpy.types.Operator):
    # The docstring is used by Blender for its description, so we do not use
    # line breaks. A period is also automatically added by Blender.
    'Render an image of relationships between selected bones only; available only when at least one bone is selected in armature Edit Mode or Pose Mode' # noqa

    # This attribute is used by Blender as the operator’s Python ID.
    bl_idname = 'armature.rig_graphviz_for_selected_bones_only'
    # This attribute is used by Blender as the operator’s menu label.
    bl_label = 'Render Graph for Selected Bones Only'

    @classmethod
    def poll(self, context):
        """
        Blender calls this method to determine whether the operator may be
        activated. Armature Edit Mode or Pose Mode must be active, and at least
        one bone must be selected.
        """
        if context.mode != 'EDIT_ARMATURE' and context.mode != 'POSE':
            return False

        if not len(get_selected_bones(context)):
            return False

        return True

    def execute(self, context):
        """
        Blender calls this method when the operator is activated. It will
        start the operator’s action and continue it as a running modal with
        regular timer events (see the modal method).
        """
        # This is an armature scene object.
        active_object = context.view_layer.objects.active

        selected_bones = get_selected_bones(context)

        included_bone_set = set(
            normalize_symmetric_bones_to_left_side(
                bones=selected_bones,
                armature_object=active_object,
            ),
        )

        def is_bone_unselected(bone, armature_object):
            return bone not in included_bone_set

        graph_data = analyze_rig_graph(
            # The active armature scene object is the only scene object that
            # will be scanned.
            [active_object],
            # This predicate will exclude any bone that is not selected from
            # the graph.
            is_bone_excluded=is_bone_unselected,
        )

        time_string = create_time_description()
        title = f'{time_string} • {len(included_bone_set)} Selected Bones Only'

        return run_rig_graphviz_operator(
            self,
            context=context,
            graph_data=graph_data,
            output_filename=get_rig_output_filename(context),
            create_success_message=lambda output_file_path:
                create_bone_render_success_message(
                    output_file_path,
                    included_bone_set,
                ),
            title=title,
        )

    def invoke(self, context, event):
        """
        Blender calls this method when the operator is activated by a UI event
        (e.g., by using one of its menu items).
        """
        # There is no extra information needed from the event, so we need to
        # do nothing extra before delegating to the execute method.
        return self.execute(context)


class OBJECT_OT_rig_graphviz_legend(bpy.types.Operator):
    # The docstring is used by Blender for its description, so we do not use
    # line breaks. A period is also automatically added by Blender.
    'Render an image explaining the rig graphs’ graphics.'

    # This attribute is used by Blender as the operator’s Python ID.
    bl_idname = 'object.rig_graphviz_legend'
    # This attribute is used by Blender as the operator’s menu label.
    bl_label = 'Render Graph Legend'

    def execute(self, context):
        """
        Blender calls this method when the operator is activated. It will
        start the operator’s action and continue it as a running modal with
        regular timer events (see the modal method).
        """
        graph_data = create_legend_data()

        return run_rig_graphviz_operator(
            self,
            context=context,
            graph_data=graph_data,
            output_filename='Rig Legend',
            # The legend needs to arrange increasing node ranks from left to
            # right, not up to down, in order to have the correct arrangement
            # with its nodes and invisible edges.
            rankdir='LR',
            create_success_message=create_legend_render_success_message
        )

    def invoke(self, context, event):
        """
        Blender calls this method when the operator is activated by a UI event
        (e.g., by using one of its menu items).
        """
        # There is no extra information needed from the event, so we need to
        # do nothing extra before delegating to the execute method.
        return self.execute(context)


class RIG_MT_rig_graphviz(bpy.types.Menu):
    """
    The operator submenu for the Rig Graphviz add-on.
    """

    # This attribute is used by Blender as the operator’s menu label.
    bl_label = 'Rig Graphviz'

    def draw(self, context):
        """
        Blender calls this method when drawing the menu.
        """
        self.layout.operator(
            OBJECT_OT_rig_graphviz_with_all_bones.bl_idname,
            text=OBJECT_OT_rig_graphviz_with_all_bones.bl_label,
            icon='HIDE_OFF',
        )
        self.layout.operator(
            OBJECT_OT_rig_graphviz_with_visible_bones.bl_idname,
            text=OBJECT_OT_rig_graphviz_with_visible_bones.bl_label,
            icon='HIDE_ON',
        )
        self.layout.operator(
            ARMATURE_OT_rig_graphviz_selected_bones_only.bl_idname,
            text=ARMATURE_OT_rig_graphviz_selected_bones_only.bl_label,
            icon='RESTRICT_SELECT_OFF',
        )
        self.layout.separator()
        self.layout.operator(
            OBJECT_OT_rig_graphviz_legend.bl_idname,
            text=OBJECT_OT_rig_graphviz_legend.bl_label,
            icon='INFO',
        )


def place_operators_in_menu(self, context):
    """
    This function places the Rig Graphviz operators into the layout of its
    receiver, which is expected to be a menu.
    """
    self.layout.separator()
    self.layout.menu('RIG_MT_rig_graphviz')


# This tuple will be used with bpy.utils.register_classes_factory.
addon_classes = (
    ArmatureGraphvizAddonPreferences,
    RIG_MT_rig_graphviz,
    OBJECT_OT_rig_graphviz_with_all_bones,
    OBJECT_OT_rig_graphviz_with_visible_bones,
    ARMATURE_OT_rig_graphviz_selected_bones_only,
    OBJECT_OT_rig_graphviz_legend,
)


# These two functions respectively register and unregister the add-on classes
# with Blender.
register_addon_classes, unregister_addon_classes = (
    bpy.utils.register_classes_factory(addon_classes)
)


def register():
    """
    This function is used by Blender when enabling the add-on – or when Blender
    is opened with the add-on already enabled.
    """
    register_addon_classes()

    # Append the operators to the Object Mode’s Object menu.
    bpy.types.VIEW3D_MT_object.append(place_operators_in_menu)

    # Append the operators to the armature Edit Mode’s Armature menu.
    bpy.types.VIEW3D_MT_edit_armature.append(place_operators_in_menu)

    # Append the operators to the armature Pose Mode’s Pose menu.
    bpy.types.VIEW3D_MT_pose.append(place_operators_in_menu)


def unregister():
    """
    This function is used by Blender when disabling the add-on – or when
    Blender quits with the add-on enabled.
    """
    unregister_addon_classes()

    # Append the render operator to the Object Mode’s Object menu.
    bpy.types.VIEW3D_MT_object.remove(place_operators_in_menu)

    # Remove the operator from the armature Edit Mode’s Armature menu.
    bpy.types.VIEW3D_MT_edit_armature.remove(place_operators_in_menu)

    # Remove the operator from the armature Pose Mode’s Pose menu.
    bpy.types.VIEW3D_MT_pose.remove(place_operators_in_menu)


# If the script is being run directly from Blender's Text editor, then register
# the add-on without installing it.
if __name__ == '__main__':
    register()
