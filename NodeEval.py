'''
@name     NodeEval
@package  sublime_plugin
@author   Derek Anderson
@requires NodeJS

This Sublime Text 2 plugin adds NodeJS "eval" functionality
to the right click context menu, etc.

Usage: Make a selection (or not), Choose NodeEval from the 
context menu and see the results in the console.

'''

import sublime, sublime_plugin, os
from subprocess import Popen, PIPE, STDOUT


#
# Create a new output, insert the message and show it
#
def panel(view, message, region):
  s = sublime.load_settings("NodeEval.sublime-settings")
  window = view.window()
  # Should we set the clipboard?
  clipboard = s.get('copy_to_clipboard')
  if clipboard: sublime.set_clipboard( message )
  # determine the output format
  output = s.get('output')
  clear = s.get('overwrite_output')

  # Output to a Console (panel) view
  if output == 'console':
    p = window.get_output_panel('nodeeval_panel')
    p_edit = p.begin_edit()
    p.insert(p_edit, p.size(), message)
    p.end_edit(p_edit)
    p.show(p.size())
    window.run_command("show_panel", {"panel": "output.nodeeval_panel"})

  # Output to a new file
  elif output == 'new':
    active = False
    for tab in window.views():
      if 'NodeEval::Output' == tab.name(): active = tab
    if active: 
      _output_to_view(view, active, message, clear=clear)
      window.focus_view(active)
    else: scratch(view, message, "NodeEval::Output", clear=clear)

  # Output to the current view/selection (work performed in the calling method)
  elif output == 'replace':
    edit = view.begin_edit()
    view.replace(edit, region, message)
    view.end_edit(edit)

  elif output == 'clipboard':
    sublime.set_clipboard( message )

  else:
    return False




#
# Helper to output views
#
def _output_to_view(v, output_file, output, clear=True, syntax="Packages/JavaScript/JavaScript.tmLanguage"):
    output_file.set_syntax_file(syntax)
    edit = output_file.begin_edit()
    if clear:
      region = sublime.Region(0, output_file.size())
      output_file.erase(edit, region)
    output_file.insert(edit, 0, output)
    output_file.end_edit(edit)

# 
# Helper to output a new Scratch (temp) file
# 
def scratch(v, output, title=False, **kwargs):
    scratch_file = v.window().new_file()
    if title:
      scratch_file.set_name(title)
    scratch_file.set_scratch(True)
    _output_to_view(v, scratch_file, output, **kwargs)
    scratch_file.set_read_only(False)


#
# Eval the "data" (message) with basically: `node -p -e data`
#
def eval(view, data, region):
  # get the current working dir, if one exists...
  cwd = view.file_name()
  cwd = os.path.dirname(cwd) if cwd else None
  s = sublime.load_settings("NodeEval.sublime-settings")
  node_command = os.path.normpath(s.get('node_command'))
  try:
    # node = Popen([node_command, "-p", data.encode("utf-8")], stdout=PIPE, stderr=PIPE)
    node = Popen([node_command, "-p"], cwd=cwd, stdin=PIPE, stdout=PIPE, stderr=PIPE)
    node.stdin.write( data.encode("utf-8") )
    result, error = node.communicate()
  except OSError,e:
    error_message = """
 Please check that the absolute path to the node binary is correct:
 Attempting to execute: %s
 Error: %s
    """ % (node_command, e[1])
    panel(view, error_message)
    return False

  message = error if error else result
  panel(view, message, region)



#
# Get the selected text regions (or the whole document) and process it
#
class NodeEvalCommand(sublime_plugin.TextCommand):
  def run(self, edit):
    # save the document size
    view_size = self.view.size()
    # get selections
    regions = self.view.sel()
    num = len(regions)
    x = len(self.view.substr(regions[0]))
    # select the whole document if there is no user selection
    if num <= 1 and x == 0:
      regions.clear()
      regions.add( sublime.Region(0, view_size) )

    # get current document encoding or set sane defaults
    encoding = self.view.encoding()
    if encoding == 'Undefined':
      encoding = 'utf-8'
    elif encoding == 'Western (Windows 1252)':
      encoding = 'windows-1252'

    # eval selections
    for region in regions:
      data = self.view.substr(region)
      eval(self.view, data, region)
