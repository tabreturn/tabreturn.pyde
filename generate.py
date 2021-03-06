import os
import re
import shutil

from jinja2 import Environment, FileSystemLoader
from lexer import ProcessingPyLexer
from pygments import highlight
from pygments.formatters import HtmlFormatter
from pyp5js.commands import transcrypt_sketch
from pyp5js.config import SKETCHBOOK_DIR

EXAMPLES_DIR = os.path.abspath(os.path.join(SKETCHBOOK_DIR, os.pardir))
DL = '___' # delimiter for file names

# delete any partially transcribed files from a previous run

if os.path.exists(SKETCHBOOK_DIR):
    shutil.rmtree(SKETCHBOOK_DIR)

# create _site directory

SITE_DIR = '_site'

if os.path.exists(SITE_DIR):
    shutil.rmtree(SITE_DIR)

os.makedirs(SITE_DIR)

# rename and copy sketches to _temp directory

for category in os.listdir(EXAMPLES_DIR):
    # skip over gitignore and other hidden files
    if category[0] == '.':
        continue

    category_dir = os.path.join(EXAMPLES_DIR, category)

    for sub_category in os.listdir(category_dir):
        # rename any sub-category paths incompatible with pyp5js
        sc_words = sub_category.split()
        sc_title = ' '.join(word[0].upper() + word[1:] for word in sc_words)
        sc_final = sc_title.replace(' ', '').replace('-', '_')
        sub_category_dir = os.path.join(EXAMPLES_DIR, category, sub_category)

        for sketch in os.listdir(sub_category_dir):
            sketch_path = os.path.join(sub_category_dir, sketch)
            new_name = ''.join([category, DL, sc_final, DL, sketch])
            shutil.copytree(sketch_path, os.path.join(SKETCHBOOK_DIR, new_name))

# copy .pyde file (in _temp directory) to a .py file (for p5js conversion)

for temp_sketch in os.listdir(SKETCHBOOK_DIR):
    temp_sketch_dir = os.path.join(SKETCHBOOK_DIR, temp_sketch)

    for sketch_file in os.listdir(temp_sketch_dir):

        if sketch_file[-5:] == '.pyde':
            shutil.copy(
              os.path.join(temp_sketch_dir, sketch_file),
              os.path.join(temp_sketch_dir, temp_sketch + '.py')
            )


def add_draw_and_setup_functions(code):
    """Add draw() and setup() functions for pyp5js compatibility"""
    flush_size_function = re.compile(r'(^size\()(.*)', flags=re.MULTILINE)
    indent_size_function = r'def setup():\n    \1\2\n\ndef draw():\n'
    code = flush_size_function.sub(indent_size_function, code)
    result = ''
    indent_mode = False
    def_draw = 'def draw():'
    # indent everything after draw() function (up to next def)
    for line in code.split('\n'):

        if not indent_mode and line[0:len(def_draw)] == def_draw:
            indent_mode = True
            result += line
            continue

        if indent_mode and line[:4] == 'def ':
            indent_mode = False

        if indent_mode:
            result += '    {}\n'.format(line)

        else:
            result += line + '\n'

    return result


# transcribe sketches using pyp5js

for temp_sketch in os.listdir(SKETCHBOOK_DIR):

    for sketch_file in os.listdir(os.path.join(SKETCHBOOK_DIR, temp_sketch)):

        if sketch_file[-3:] == '.py':
            py_file = os.path.join(SKETCHBOOK_DIR, temp_sketch, sketch_file)
            py_read = open(py_file, 'rt')
            py_content = py_read.read()
            # pyp5js compatibility workarounds
            pc = py_content
            # workaround for pyp5js global variables issue
            # https://berinhard.github.io/pyp5js/#known-issues-and-differences-to-the-processingpy-and-p5js-ways-of-doing-things
            # find all global variables
            global_vars = re.findall('global (.*)', pc)
            # add placeholder variables to global scope
            for vars in global_vars:
                nones = 'None, ' * len(vars.split(','))
                pc = '{} = {}\n{}'.format(vars, nones[:-2], pc)
            # if the file is the main sketch file ...
            if sketch_file[:-3] == temp_sketch:
                # ... add a setup() and draw() function if size() isn't indented
                if pc.find('    size(') < 0:
                    pc = add_draw_and_setup_functions(pc)
                # ... replace size() with createCanvas() function for pyp5js compatibility
                pc = pc.replace('size(', 'createCanvas(')
                # ... replace P3D with WEBGL for pyp5js compatibility
                pc = pc.replace('P3D)', 'WEBGL)')
            # remove any instances of beginDraw() and endDraw() for pyp5js compatibility
            pc = re.sub(r'.*beginDraw\(\)', r'', pc)
            pc = re.sub(r'.*endDraw\(\)', r'', pc)
            # replace any instances of mousePressed variables for pyp5js compatibility
            pc = re.sub(r'mousePressed(?!.*\()', r'mouseIsPressed', pc)
            # replace specular functions for pyp5js compatibility
            pc = pc.replace('lightSpecular(', 'specularColor(')
            pc = pc.replace('specular(', 'specularMaterial(')
            # replace loadShape() and shape() functions for pyp5js compatibility
            if pc.find('WEBGL)') < 0:
                pc = pc.replace('loadShape(', 'loadImage(')
                pc = pc.replace('shape(', 'image(')
            else:
                pc = pc.replace('loadShape(', 'loadModel(')
                pc = pc.replace('shape(', 'model(')
            # insert pyp5js import line
            pc = 'from pyp5js import *\n' + pc
            # replace any println() functions for print()
            pc = pc.replace('println(', 'print(')
            # replace any createFont() functions for loadFont()
            pc = pc.replace('createFont(', 'loadFont(')

            py_read.close()
            sketch_write = open(py_file, 'wt')
            sketch_write.write(pc)
            sketch_write.close()

    transcrypt_sketch(temp_sketch)

# move transcribed sketches to _site directory

for temp_sketch in os.listdir(SKETCHBOOK_DIR):
    target_dir = os.path.join(SKETCHBOOK_DIR, temp_sketch, 'target')
    data_dir = os.path.join(SKETCHBOOK_DIR, temp_sketch, 'data')
    # check if a data directory exists
    if os.path.exists(data_dir):
        data_files = os.listdir(data_dir)
        # copy any files from the data sub-directory into the target directory
        for data_file in data_files:
            data_file_path = os.path.join(data_dir, data_file)
            shutil.copy(data_file_path, target_dir)

    destination_dir = os.path.join(SITE_DIR, temp_sketch)
    shutil.move(target_dir, destination_dir)

# load templates

env = Environment(loader=FileSystemLoader('templates'))

templates = {
  'index': env.get_template('index.html'),
  'example': env.get_template('example.html'),
}

# read all sketch data into a list

sketches_data = []

for temp_sketch in os.listdir(SITE_DIR):
    temp_sketch_path = os.path.join(SKETCHBOOK_DIR, temp_sketch)
    pyde_file = temp_sketch.split(DL)[-1] + '.pyde'
    temp_sketch_file = os.path.join(temp_sketch_path, pyde_file)
    sketch_read = open(temp_sketch_file, 'rt')
    sketch_content = sketch_read.read()
    # separate out description code and metadata
    sketch_description = re.findall('"""[\s\S]*?"""', sketch_content)[0]
    sketch_code = sketch_content.replace(sketch_description, '')
    sketch_description = sketch_description.replace('"""', '')
    sketch_description = sketch_description.split('\n', 2)[2]
    sketch_code = highlight(sketch_code, ProcessingPyLexer(), HtmlFormatter())
    cat_subcat_sketch = temp_sketch.split(DL)
    sketches_data.append({
      'file_name': temp_sketch,
      'category': cat_subcat_sketch[0],
      'sub_category': cat_subcat_sketch[1],
      'title': cat_subcat_sketch[2],
      'description': sketch_description,
      'code': sketch_code
    })

# generate landing page

index_html = templates['index'].render(metadata=sketches_data)

with open(os.path.join(SITE_DIR, 'index.html'), 'w') as file:
    file.write(index_html)

# copy static assets into _site directory

for asset in os.listdir('static'):
    asset_source = os.path.join('static', asset)
    asset_destination = os.path.join(SITE_DIR, asset)
    shutil.copyfile(asset_source, asset_destination)

# generate example pages

for sketch in sketches_data:
    example_html = templates['example'].render(contents=sketch)
    example_dir = os.path.join(SITE_DIR, sketch['file_name'])

    with open(os.path.join(example_dir, 'index.html'), 'w') as file:
        file.write(example_html)
