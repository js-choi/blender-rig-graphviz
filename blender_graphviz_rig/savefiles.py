# This module is licensed by its authors under the GNU Affero General Public
# License 3.0.

"""
This module takes strings that represent directed graphs with the DOT language,
and it renders them into image files using Graphviz.
"""

import itertools
import shutil
import os
import errno
import asyncio

output_file_extension = '.png'


def save_temp_dot_source_file(dot_text, dot_source_file_path):
    """
    This function synchronously saves the given DOT text document (a string)
    into a text file at the given dot_source_file_path. Once complete, it
    returns None.
    """
    # The mode='w+' means that the file is wiped (truncated) then written to.
    with open(dot_source_file_path, mode='w+') as file:
        file.write(dot_text)


class GraphvizNotFoundError(Exception):
    """
    This error class is used to indicate that the system shell could not find
    the Graphviz DOT application.
    """
    pass


class GraphvizOutputError(Exception):
    """
    This error class is used to indicate a problem raised by the Graphviz
    application itself, such as a DOT-language syntax error in an input or
    inability to save an image file at a given output location.
    """
    pass


async def exec_graphviz_async(
    dot_command,
    dot_source_file_path,
    output_file_path,
):
    """
    This asynchronous function executes the Graphviz command on the given DOT
    source file. Once complete, it returns None. If it encounters problems
    while rendering and saving, it may raise an OSError, a
    GraphvizNotFoundError, or a GraphvizOutputError.
    """
    try:
        # Create an OS process running Graphviz. The create_subprocess_exec
        # function escapes command-argument strings and prevents shell-injection
        # attacks.
        proc = await asyncio.create_subprocess_exec(
            # The dot command from Graphviz must be installed into the shell
            # path.
            dot_command,
            # The new image’s file path.
            '-o', output_file_path,
            # The new image is rendered as a PNG.
            '-T', 'png',
            # The new image’s DPI is at 200 to prevent ugly pixelation.
            '-Gdpi=300',
            # The new image is to have a bigger padding than the default (which
            # is 0.555, or 4 typographic points).
            '-Gpad=1',
            # The input DOT source file’s path.
            dot_source_file_path,
            # Pipe the process’s stderr text into a StreamWriter.
            stderr=asyncio.subprocess.PIPE,
        )
        # Waits for the process to finish and gets the resulting stderr
        # StreamWriter.
        _, stderr = await proc.communicate()
        # Graphviz returns an exit code of 0 if it is successful; it returns a
        # non-zero exit code if it is not successful.
        if proc.returncode:
            # When Graphviz returns an error exit code, then the image saving
            # was unsuccessful.
            raise GraphvizOutputError(stderr.decode())

    except OSError as err:
        if err.errno == errno.ENOENT:
            # In this case, Graphviz has not been installed on the OS, so its
            # executable applications are not available in the system shell.
            raise GraphvizNotFoundError()
        else:
            # In this case, a strange and unexpected error from the OS
            # occurred while running Graphviz DOT.
            raise err

    # If Graphviz successfully rendered and saved the image file, then this
    # function will return None.


def get_unused_suffixed_filename(directory_path, filename, file_extension):
    """
    This function returns an unused filename string, consisting of filename –
    then “.0”, “.1”, “.2”, “.3”, “.4”, “.5”, “.6”, “.7”, “.8”, “.9”, “.10”, or
    whatever is first unused – then the file_extension.
    """
    base_filename = os.path.join(directory_path, filename)

    # This iterator indefinitely yields consecutive integers starting from 0.
    fresh_integers = itertools.count()

    for i in fresh_integers:
        trial_filename = f'{base_filename}.{i}{file_extension}'
        if not os.path.exists(trial_filename):
            return trial_filename


def back_up_file(directory_path, filename, file_extension):
    """
    If a file exists at the given directory_path with the given filename and
    file_extension, then this function copies it to a backup file named
    filename – then “.0”, “.1”, “.2”, “.3”, “.4”, “.5”, “.6”, “.7”, “.8”, “.9”,
    “.10”, or whatever is first unused – then the file_extension.
    """
    unused_suffixed_filename = get_unused_suffixed_filename(
        directory_path,
        filename,
        file_extension,
    )
    source_file_path = (
        os.path.join(directory_path, filename) + file_extension
    )
    destination_file_path = (
        os.path.join(directory_path, unused_suffixed_filename)
    )

    try:
        shutil.copyfile(source_file_path, destination_file_path)

    except OSError as err:
        if err.errno == errno.ENOENT:
            # In this case, there is no file yet to back up.
            return
        else:
            # In this case, a strange and unexpected error from the OS occurred
            # while copying the file, such as lack of writing permissions in
            # directory_path.
            raise err


async def save_files_async(
    dot_text,
    dot_command,
    dot_source_file_path,
    output_directory_path,
    output_filename,
):
    """
    This asynchronous function sequentially and asynchronously performs all of
    the add-on’s file-saving tasks with the given dot_text and file paths.
    """
    save_temp_dot_source_file(dot_text, dot_source_file_path)

    back_up_file(output_directory_path, output_filename, output_file_extension)

    output_file_path = (
        os.path.join(output_directory_path, output_filename)
        + output_file_extension
    )

    await exec_graphviz_async(
        dot_command,
        dot_source_file_path,
        output_file_path,
    )

def save_files(
    dot_text,
    dot_command,
    dot_source_file_path,
    output_directory_path,
    output_filename,
):
    """
    This function synchronously renders and creates a image file using
    Graphviz. It returns when the task is complete.

    The dot_text must be a string that expresses a directed graph. The string
    will be synchronously saved in the given dot_source_file_path as a text
    DOT-source file.

    The dot_command must be a string like 'dot' (for Linux and macOS) or
    'C:\\Program Files\\Graphviz\\bin\\dot.exe' (for Windows), which the shell
    will run to render that text DOT-source file into an image at the given
    output_directory_path and output_filename (with a “.png”).

    If a PNG image file already exists at the given location, then it will be
    copied to a backup file using the back_up_file function.

    Any error returned by Graphviz or the OS will respectively raise a
    RuntimeError or an OSError.
    """
    return asyncio.run(
        save_files_async(
            dot_text,
            dot_command,
            dot_source_file_path,
            output_directory_path,
            output_filename,
        ),
    )
