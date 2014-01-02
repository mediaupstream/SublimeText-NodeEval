'''
@name     NodeEval
@package  sublime_plugin
@author   Derek Anderson
@requires NodeJS

This Sublime Text 2 & 3 plugin adds NodeJS "eval" functionality
to the right click context menu, etc.

Usage: Make a selection (or not), Choose NodeEval from the 
context menu and see the results in the console.

'''

import sublime, sublime_plugin, os, time
from functools import partial
from subprocess import Popen, PIPE, STDOUT
import subprocess

import sys

PY3 = sys.version_info[0] >= 3
if PY3:
  from imp import reload 
reload(sys)

if not PY3:
  sys.setdefaultencoding('utf-8')  

if not PY3:
  import thread

import threading

ST3 = int(sublime.version()) >= 3000

# 
# Globals
# 
g_enabled = False
g_view = None
g_threshold = 0
g_replace_pos = 0
# copy the current environment
g_env = os.environ.copy()
# grab any extra environment variables from settings
g_env_extra = {}
# add them to the g_env dict
if g_env_extra is not None:
  g_env.update(g_env_extra)

def plugin_loaded():
  global g_env
  global g_threshold
  global g_env_extra
  g_threshold = int (sublime.load_settings("NodeEval.sublime-settings").get('threshold'))
  g_env_extra = sublime.load_settings("NodeEval.sublime-settings").get('env')
  if g_env_extra is not None:
    g_env.update(g_env_extra)


# 
# Toggle continuous eval'ing of a selection/document
# 
class Continuous(sublime_plugin.EventListener):
  prev = 0
  def check_threshold(self, stamp):
    global g_view
    if stamp == self.prev:
      self.prev = 0
      if g_view != None: _node_eval(g_view[0], g_view[1], True)

  def on_modified(self, view):
    global g_enabled
    global g_view
    global g_threshold
    if g_enabled == False: return False
    if view.id() == g_view[0].view.id():
      stamp = time.time()
      self.prev = stamp
      sublime.set_timeout( partial(self.check_threshold, stamp), g_threshold)


#
# ST3 needs a Text Command called to insert text
#
class EvalMessageCommand(sublime_plugin.TextCommand):
  def run(self, edit, message, insert):
    if insert is True:
      self.view.insert(edit, self.view.size(), message)
    else:
      self.view.replace(edit, sublime.Region(insert[0], insert[1]), message)

#
# Create a new output, insert the message and show it
#
g_output_panel = None
def panel(view, message, region, clear=False):
  if ST3 and not isinstance(message, str):
    message = str(message, "utf-8")

  s = sublime.load_settings("NodeEval.sublime-settings")
  window = view.window()

  # Should we set the clipboard?
  clipboard = s.get('copy_to_clipboard')
  if clipboard: sublime.set_clipboard( message )
  # determine the output format
  output = s.get('output')

  # Output to a Console (panel) view or a new file
  if output == 'console' or output == 'new':
    _output_to_view(view, g_output_panel, message, clear=clear)
    return False

  # Output to the current view/selection (work performed in the calling method)
  global g_replace_pos
  if output == 'replace':

    if ST3:
      view.run_command("eval_message", 
        {"message": message, "insert": [g_replace_pos, g_replace_pos] })
    else:
      edit = view.begin_edit()
      view.insert(edit, g_replace_pos, message)
      view.sel().clear()
      view.end_edit(edit)

    g_replace_pos += len(message.decode('utf-8')) #len(message)
    return False

  if output == 'clipboard':
    sublime.set_clipboard( sublime.get_clipboard() + message )
    return False
  
  return False

#
# Helper to output views
#
def _output_to_view(v, output_file, output, clear=True):
    # syntax="Packages/JavaScript/JavaScript.tmLanguage"
    # output_file.set_syntax_file(syntax)
    if ST3:
      if clear:
        output_file.run_command("eval_message", {"message": output, "insert": [0, output_file.size()]})
      else:
        output_file.run_command("eval_message", {"message": output, "insert": True })
    else:
      edit = output_file.begin_edit()
      if clear:
        region = sublime.Region(0, output_file.size())
        output_file.erase(edit, region)
      output_file.insert(edit, output_file.size(), output)
      output_file.end_edit(edit)
      #scroll to the last line of the view
      output_file.run_command("goto_line", {"line": output_file.rowcol(output_file.size())[0]+1})
      output_file.sel().clear()
      output_file.sel().add(output_file.size())

# 
# Helper to output a new Scratch (temp) file
# 
def scratch(v, title=False):
    scratch_file = v.window().new_file()
    if title:
      scratch_file.set_name(title)
    scratch_file.set_scratch(True)
    #_output_to_view(v, scratch_file, output, **kwargs)
    scratch_file.set_read_only(False)
    return scratch_file

def _out_thread(view, node, region):
  while True:
    out_line = node.stdout.readline()
    if out_line:
      write = partial(panel, view, out_line, region)
      sublime.set_timeout(write, 1)

def _err_thread(view, node, region):
  while True:
    err_line = node.stderr.readline()
    if err_line:
      write = partial(panel, view, err_line, region)
      sublime.set_timeout(write, 1)

#
# Eval the "data" (message) with basically: `node -p -e data`
#
def eval(view, data, region):
  # get the current working dir, if one exists...
  cwd = view.file_name()
  cwd = os.path.dirname(cwd) if cwd else None
  errors_to_catch = (FileNotFoundError, OSError) if ST3 else OSError
  
  s = sublime.load_settings("NodeEval.sublime-settings")
  clear = s.get('overwrite_output')
  output = s.get('output')
  options = s.get('command_options')
  window = view.window()

  global g_output_panel
  if output == 'console':
    if g_output_panel is None:
      g_output_panel = window.get_output_panel('nodeeval_panel')
    window.run_command("show_panel", {"panel": "output.nodeeval_panel"})
  
  if output == 'new':
    for tab in window.views():
      if 'NodeEval::Output' == tab.name(): 
        g_output_panel = tab
        window.focus_view(tab)
        break 
    else:
        g_output_panel = scratch(view, 'NodeEval::Output')

  if output == 'replace':
    global g_replace_pos
    g_replace_pos = region.begin()
    edit = view.begin_edit()
    view.replace(edit, region, '')
    view.end_edit(edit)

  if output == 'clipboard':
    sublime.set_clipboard('')

  if clear:
    panel(view, "", region, True);

  if ST3:
   code = bytes(data, 'UTF-8')
  else:
   code = data.encode("utf-8")

  try:
    s = sublime.load_settings("NodeEval.sublime-settings")
    node_command = os.path.normpath(s.get('node_command'))
    
    if os.name == 'nt':
      # Suppress showing the cmd.exe window for that split second
      startupinfo = subprocess.STARTUPINFO()
      startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
      node = Popen([node_command] + options + ["-e", code], cwd=cwd, stdin=PIPE, stdout=PIPE, stderr=PIPE, startupinfo=startupinfo)
    else:
      node = Popen([node_command] + options + ["-e", code], cwd=cwd, stdin=PIPE, stdout=PIPE, stderr=PIPE, close_fds=True, env=g_env)

    if not ST3:
      thread.start_new_thread(_out_thread, (view, node, region))
      thread.start_new_thread(_err_thread, (view, node, region))
      return True
    else:
      # result, error = node.communicate()
      out_thread = threading.Thread(target=_out_thread, args=(view, node, region))
      err_thread = threading.Thread(target=_err_thread, args=(view, node, region))
      out_thread.start()
      err_thread.start()
      return True      

  except errors_to_catch as e:
    error_message = """
 Please check that the absolute path to the node binary is correct:
 Attempting to execute: %s
 Error: %s
    """ % (node_command, e)
    panel(view, error_message, False)
    return False
  # message = error if error else result
  # panel(view, message, region)


#
# Get the selected text regions (or the whole document) and process it
#
class NodeEvalCommand(sublime_plugin.TextCommand):
  def run(self, edit, continuous=False):
    global g_enabled
    global g_view

    if continuous and g_enabled == False:
      g_enabled = True
      g_view = self, edit
    elif continuous and g_enabled == True:
      g_enabled = False
      g_view = None
    # Do it!
    _node_eval(self, edit)



def _node_eval(s, edit, focus=False):
  # save the document size
    view_size = s.view.size()
    # get selections
    regions = s.view.sel()
    n_regions = list(regions)
    num = len(regions)
    x = len(s.view.substr(regions[0]))
    # select the whole document if there is no user selection
    if num <= 1 and x == 0 or focus:
      regions.clear()
      regions.add( sublime.Region(0, view_size) )
    # eval selections
    for region in regions:
      data = s.view.substr(region)
      eval(s.view, data, region)
      #thread.start_new_thread(eval, (s.view, data, region))

    regions.clear()
    regions.add(n_regions[0])

    if focus:
      s.view.window().focus_view( s.view )
