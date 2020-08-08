try:
    import locale
    locale.setlocale(locale.LC_ALL, '')
except BaseException:
    pass

import os, sys, codecs, shutil, subprocess, pprint

import docutils, docutils.core

# Pyhton2 compatibility
try:
    from html import unescape
except ImportError:
    from cgi import unescape


from .RevealTranslator import RevealTranslator, HTMLWriter

# Import custom directives
from .TwoColumnsDirective import *
from .PygmentsDirective import *
from .VideoDirective import *
from .PlotDirective import *
from .SmallRole import *
from .VspaceRole import *
from .ClassDirective import *
from .ClearDirective import *
from .TemplateDirective import *


class Parser:
    """Class converting a stand-alone reST file into a Reveal.js-powered HTML5 file, using the provided options."""

    def __init__(self, input_file, output_file='', resources=None, debug=None):
        """ Constructor of the Parser class.

        ``create_slides()`` must then be called to actually produce the presentation.

        Arguments:

            * input_file : name of the reST file to be processed (obligatory).

            * output_file: name of the HTML file to be generated (default: same as input_file, but with a .html extension).

            * resources: 'central', 'local', or 'inline': how external resources should be handled:

              - central (default): "Use centralized resources from where rstslide is installed
              - local: Copy needed resources to a directory <outfile>-resources
              - inline: Embedd all resources into a single file HTML document
              - online: Use links to online resources when possible (internet needed to show presentation)

            * debug: set to true to produce debug output on stdout

        The input rst file allows the following settings in the first field list:

            * theme: the name of the theme to be used ({**default**, beige, night}).

            * transition: the transition between slides ({**default**, cube, page, concave, zoom, linear, fade, none}).

            * stylesheet: a custom CSS file which extends or replaces the used theme.

            * pygments_style: the style to be used for syntax color-highlighting using Pygments. The list depends on your Pygments version, type::

                from pygments.styles import STYLE_MAP
                print STYLE_MAP.keys()

            * vertical_center: boolean stating if the slide content should be vertically centered (default: False).

            * horizontal_center: boolean stating if the slide content should be horizontally centered (default: False).

            * title_center: boolean stating if the title of each slide should be horizontally centered (default: False).

            * footer: boolean stating if the footer line should be displayed (default: False).

            * page_number: boolean stating if the slide number should be displayed (default: False).

            * controls: boolean stating if the control arrows should be displayed (default: False).

            * firstslide_template: template string defining how the first slide will be rendered in HTML.

            * footer_template: template string defining how the footer will be rendered in HTML.

        The ``firstslide_template`` and ``footer_template`` can use the following substitution variables:

            * %(title)s : will be replaced by the title of the presentation.

            * %(subtitle)s : subtitle of the presentation (either a level-2 header or the :subtitle: field, if any).

            * %(author)s : :author: field (if any).

            * %(institution)s : :institution: field (if any).

            * %(email)s : :email: field (if any).

            * %(date)s : :date: field (if any).

            * %(is_author)s : the '.' character if the :author: field is defined, '' otherwise.

            * %(is_subtitle)s : the '-' character if the subtitle is defined, '' otherwise.

            * %(is_institution)s : the '-' character if the :institution: field is defined, '' otherwise.

        You can also use your own fields in the templates.

        """

        self.input_file = input_file
        self.output_file = output_file

        self.curr_dir = os.path.dirname(os.path.realpath(self.output_file))
        self.output_name = os.path.splitext(os.path.basename(output_file))[0]
        self.resource_dir_abspath = None
        self.resource_dir_relpath = None

        if resources:
            self.resources = resources
        else:
            self.resources = 'central'

        self.debug = debug

        # Path to rsttools directory
        self.rsttools_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))

        # Path to rstslide resource directory
        self.rstslide_root = os.path.join(self.rsttools_root, 'rstslide')

        # Path to reveal
        self.reveal_root = os.path.join(self.rsttools_root, 'external', 'reveal.js', 'dist')
        self.reveal_plugins_root = os.path.join(self.rsttools_root, 'reveal-plugins')

        # Path to MathJax
        self.mathjax_root = os.path.join(self.rsttools_root, 'external', 'mathjax', 'node_modules', 'mathjax','es5')

        self.settings = {}

        # Css to embed in the document
        self.settings['css_embedd'] = []

        # Extra css files to add
        self.settings['css_files'] = []

        # Javascript code to embed in the document
        self.settings['js_embedd'] = []

        # Extra js files to add
        self.settings['js_files'] = []

        # Style
        self.settings['reveal_theme'] = 'white'
        self.settings['transition'] = 'fade'
        self.settings['pygments_style'] = 'default'
        self.settings['stylesheet'] = ''
        self.settings['vertical_center'] = False
        self.settings['horizontal_center'] = False
        self.settings['title_center'] = False
        self.settings['write_footer'] = False
        self.settings['page_number'] = False
        self.settings['controls'] = False

        # Template for the first slide
        self.settings['firstslide_template'] = ''

        # Template for the footer
        self.settings['footer_template'] = ''

        # Initalization html for reveal.js
        self.settings['init_html'] = ''

    def create_slides(self):
        """Creates the HTML5 presentation based on the arguments given to the constructor."""

        self._setup()

        with codecs.open(self.input_file, 'r', 'utf8') as infile:
            source = infile.read()

        self.doctree = docutils.core.publish_doctree(source)
        self.settings = self._parse_docinfo(self.doctree, self.settings)

        # Create the writer and retrieve the parts
        self.html_writer = HTMLWriter()
        self.html_writer.translator_class = RevealTranslator
        #with codecs.open(self.input_file, 'r', 'utf8') as infile:
        #    self.parts = docutils.core.publish_parts(source=infile.read(), writer=self.html_writer)
        self.parts = self.publish_parts_from_doctree(self.doctree, writer=self.html_writer)

        self.settings['title'] = self.parts['title']
        self.settings['subtitle'] = self.parts['subtitle']

        if 'theme' in self.settings:
            if os.path.exists(os.path.join('themes', self.settings['theme'])):
                self.settings['theme_path'] = os.path.join('themes', self.settings['theme'])

            elif os.path.exists(os.path.join(self.rstslide_root, 'themes', self.settings['theme'])):
                self.settings['theme_path'] = os.path.join(self.rstslide_root, 'themes', self.settings['theme'])
            if 'theme_path' in self.settings:
                with codecs.open(os.path.join(self.settings['theme_path'], 'theme.rst'), 'r', 'utf8') as infile:
                    source = infile.read()
                source = self._dict_to_rst_replacements(self.settings) + source
                doctree = docutils.core.publish_doctree(source)
                self.settings = self._parse_docinfo(doctree, self.settings)
                del self.settings['theme_path']
            else:
                #print(os.path.join(self.rstslide_root, 'themes', self.settings['theme'],'theme.rst'))
                print("WARNING: theme "+self.settings['theme']+" does not exist")

        # Produce the html file
        self._produce_output()

    def _setup(self):

        cwd = os.getcwd()

        if self.resources == 'local':
            if os.path.exists(os.path.join(self.curr_dir, self.output_name + '_rstslide')):
                shutil.rmtree(os.path.join(self.curr_dir, self.output_name + '_rstslide'))
            os.makedirs(os.path.join(self.curr_dir, self.output_name + '_rstslide'))
            self.resource_dir_abspath = os.path.join(self.curr_dir, self.output_name + '_rstslide')
            self.resource_dir_relpath = self.output_name + '_rstslide'

        #source_file = os.path.abspath(os.path.join(os.path.dirname(__file__),'..','..','css','rstslide.css'))
        #shutil.copyfile(source_file, os.path.join(self.curr_dir,'rstslide.css'))

        if self.resources == 'local':
            shutil.copytree(self.reveal_root,os.path.join(self.resource_dir_abspath,'reveal'))
            shutil.copytree(self.mathjax_root,os.path.join(self.resource_dir_abspath,'mathjax'))
        
        # Generate CSS for pygments
        self.is_pygments = False
        if not self.settings['pygments_style'] == '':
            # Check if Pygments is installed
            try:
                import pygments
                self.is_pygments = True
            except BaseException:
                print('Warning: Pygments is not installed, the code will not be highlighted.')
                print('You should install it with `pip install pygments`')
                return
            os.chdir(self.curr_dir)
            if self.resources == 'inline' or self.resources == 'central':
                self.settings['css_embedd'] += [codecs.decode(subprocess.check_output(['pygmentize', '-S', self.settings['pygments_style'], "-f", "html", "-O", "bg=light"]), 'utf-8')]
            else: # self.resources == 'local':
                with codecs.open(os.path.join(self.resource_dir_abspath,'pygments.css'), 'w', 'utf8') as outfile:
                    subprocess.call(['pygmentize', '-S', self.settings['pygments_style'], "-f", "html", "-O", "bg=light"], stdout=outfile)
                self.settings['css_files'] += [os.path.join(self.resource_dir_relpath,'pygments.css')]
            os.chdir(cwd)

        if self.debug:
            sys.stdout.write("Configuration:\n")
            pprint.pprint(self.settings)

    def _produce_output(self):

        self.title = self.parts['title']
        self._analyse_metainfo()

        header = self._generate_header()
        body = self._generate_body()
        footer = self._generate_footer()

        document_content = header + body + footer

        with codecs.open(self.output_file, 'w', 'utf8') as wfile:
            wfile.write(document_content)

    def _generate_body(self):

        body = """
	        <body>
                        <div class="static-content"></div>
		        <div class="reveal">
			        <div class="slides">
%(titleslide)s
%(body)s
			        </div>
		        </div>
        """ % {'body': self.parts['body'],
               'titleslide': self.titleslide}

        return body

    def _analyse_metainfo(self):

        def clean(text):

            import re
            if len(re.findall(r'<paragraph>', text)) > 0:
                text = re.findall(r'<paragraph>(.+)</paragraph>', text)[0]
            if len(re.findall(r'<author>', text)) > 0:
                text = re.findall(r'<author>(.+)</author>', text)[0]
            if len(re.findall(r'<date>', text)) > 0:
                text = re.findall(r'<date>(.+)</date>', text)[0]
            if len(re.findall(r'<reference', text)) > 0:
                text = re.findall(r'<reference refuri="mailto:(.+)">', text)[0]
            return text

        self.meta_info = {'author': ''}

        texts = self.parts['metadata'].split('\n')
        for t in texts:
            if not t == '':
                name = t.split('=')[0]
                content = t.replace(name+'=', '')
                content = clean(content)
                self.meta_info[name] = content

        self._generate_titleslide()

    def _generate_titleslide(self):

        if self.parts['title'] != '':  # A title has been given
            self.meta_info['title'] = self.parts['title']
        elif not 'title' in self.meta_info.keys():
            self.meta_info['title'] = ''

        if self.parts['subtitle'] != '':  # defined with a underlined text instead of :subtitle:
            self.meta_info['subtitle'] = self.parts['subtitle']
        elif not 'subtitle' in self.meta_info.keys():
            self.meta_info['subtitle'] = ''

        if not 'email' in self.meta_info.keys():
            self.meta_info['email'] = ''

        if not 'institution' in self.meta_info.keys():
            self.meta_info['institution'] = ''

        if not 'date' in self.meta_info.keys():
            self.meta_info['date'] = ''

        # Separators
        self.meta_info['is_institution'] = '-' if self.meta_info['institution'] != '' else ''
        self.meta_info['is_author'] = '.' if self.meta_info['author'] != '' else ''
        self.meta_info['is_subtitle'] = '.' if self.meta_info['subtitle'] != '' else ''

        if self.settings['firstslide_template'] == "":
            self.settings['firstslide_template'] = """
    <section class="titleslide" data-state="no-toc-progress">
    <h1>%(title)s</h1>
    <h3>%(subtitle)s</h3>
    <br>
    <p><a href="mailto:%(email)s">%(author)s</a> %(is_institution)s %(institution)s</p>
    <p><small>%(email)s</small></p>
    <p>%(date)s</p>
    </section>
"""
        else:
            self.settings['firstslide_template'] = unescape(self.settings['firstslide_template'])

        self.titleslide = self.settings['firstslide_template'] % self.meta_info
        if self.settings['footer_template'] == "":
            self.settings['footer_template'] = """<b>%(title)s %(is_subtitle)s %(subtitle)s.</b> %(author)s%(is_institution)s %(institution)s. %(date)s"""

        if self.settings['write_footer']:
            self.footer_html = """<footer id=\"footer\">""" + self.settings['footer_template'] % self.meta_info + """<b id=\"slide_number\" style=\"padding: 1em;\"></b></footer>"""
        elif self.settings['page_number']:
            self.footer_html = """<footer><b id=\"slide_number\"></b></footer>"""
        else:
            self.footer_html = ""

    def _generate_header(self):

        extra_meta = ""
        if 'abstract' in self.settings:
            extra_meta += '<meta description="%(abstract)s" />\n' % {'abstract' : self.settings['abstract']}
        if 'author' in self.settings:
            extra_meta += '<meta author="%(author)s" />\n' % {'author' : self.settings['author']}
        if 'authors' in self.settings:
            for author in self.settings['authors']:
                extra_meta += '<meta author="%(author)s" />\n' % {'author' : author}

        self.settings['js_files'] = [
            os.path.join(self.mathjax_root, 'tex-svg.js'),
            os.path.join(self.reveal_root, 'reveal.js'),
        ] + self.settings['js_files']

        js_embedd = ""
        custom_js = ""
        for js_file in self.settings['js_files']:
            if self.resources == 'local':
                abspath = os.path.join(self.resource_dir_abspath,os.path.basename(js_file))
                if not os.path.exists(abspath):
                    shutil.copyfile(js_file,abspath)
                path = os.path.join(self.resource_dir_relpath,os.path.basename(js_file))
            else:
                path = js_file
            if self.resources != 'inline':
                custom_js += '<script src="%(path)s"></script>\n' % {'path' : path}
            else:
                with codecs.open(js_file, 'r', 'utf8') as infile:
                    js_embedd += '\n<!-- inlining %(path)s --->\n\n' % {'path' : path}
                    js_embedd += infile.read() + '\n\n'

        js_embedd += "\n".join(self.settings['js_embedd'])

        self.settings['css_files'] = [
            os.path.join(self.reveal_root,'reveal.css'),
            os.path.join(self.reveal_root,'theme',self.settings['reveal_theme'] + '.css'),
	    os.path.join(self.rstslide_root,'css','rstslide.css')
        ] + self.settings['css_files']

        css_embedd = ""
        custom_stylesheets = ""
        for css_file in self.settings['css_files']:
            if self.resources == 'local':
                abspath = os.path.join(self.resource_dir_abspath,os.path.basename(css_file))
                if not os.path.exists(abspath):
                    shutil.copyfile(css_file,abspath)
                path = os.path.join(self.resource_dir_relpath,os.path.basename(css_file))
            else:
                path = css_file
            if self.resources != 'inline':
                # Add the id='theme' attribute to the reveal theme in a bit of a hackish way
                if os.path.join(self.reveal_root,'theme') in path:
                    custom_stylesheets += '<link rel="stylesheet" href="%(path)s" id="theme" />\n' % {'path' : path}
                else:
                    custom_stylesheets += '<link rel="stylesheet" href="%(path)s" />\n' % {'path' : path}
            else:
                with codecs.open(css_file, 'r', 'utf8') as infile:
                    css_embedd += '\n<!-- inlining %(path)s --->\n\n' % {'path' : path}

                    css_embedd += infile.read()

        css_embedd += "\n".join(self.settings['css_embedd'])

        header = """<!doctype html>
        <html lang="en">
	        <head>
		        <meta charset="utf-8">
		        <title>%(title)s</title>
		        <meta name="description" content="%(title)s">
		        %(meta)s
		        %(extra_meta)s
                        %(custom_js)s
                        %(custom_stylesheets)s
                <script>
                   %(js_embedd)s
                </script>
                <style>
                    %(css_embedd)s

                    .reveal section {
                      text-align: %(horizontal_center)s;
                    }

                    .reveal h2{
                      text-align: %(title_center)s;
                    }
                </style>
	        </head>
        """ % {'title': self.title,
               'meta': self.parts['meta'],
               'extra_meta': extra_meta,
               'reveal_theme': self.settings['reveal_theme'],
               'reveal_root': self.reveal_root,
               'rstslide_root': self.rstslide_root,
               'horizontal_center': 'center' if self.settings['horizontal_center'] else 'left',
               'title_center': 'center' if self.settings['title_center'] else 'left',
               'css_embedd': css_embedd,
               'js_embedd': js_embedd,
               'custom_js': custom_js,
               'custom_stylesheets': custom_stylesheets }

        return header

        """
                        <script type="text/x-mathjax-config">
                          MathJax.Hub.Config({
                            jax: ["input/TeX","output/SVG"],
                            extensions: ["tex2jax.js"],
                            TeX: {
                              extensions: ["AMSmath.js","AMSsymbols.js","noErrors.js","noUndefined.js"]
                            },
                            SVG: {
                               font: "Gyre-Pagella"
                            }
                          });
                        </script>
		        <script type="text/javascript" src="%(mathjax_path)s"></script>
        """


    def _generate_footer(self):

        #if self.settings['page_number']:
        #    script_page_number = """
	#	            <script>
        #                // Fires each time a new slide is activated
        #                Reveal.addEventListener( 'slidechanged', function( event ) {
        #                    if(event.indexh > 0) {
        #                        if(event.indexv > 0) {
        #                            val = event.indexh + ' - ' + event.indexv
        #                            document.getElementById('slide_number').innerHTML = val;
        #                        }
        #                        else{
        #                            document.getElementById('slide_number').innerHTML = event.indexh;
        #                        }
        #                    }
        #                    else {
        #                        document.getElementById('slide_number').innerHTML = '';
        #                    }
        #                } );
        #            </script>"""
        #else:
        script_page_number = ""

        if self.settings['init_html']:
            footer = self.settings['init_html']
        else:
            footer = """
		        <script>
			        // Full list of configuration options available here:
			        // https://github.com/hakimel/reveal.js#configuration
			        Reveal.initialize({
				        controls: %(controls)s,
				        progress: false,
				        hash: true,
				        overview: true,
				        keyboard: true,
				        loop: false,
				        touch: true,
				        rtl: false,
				        center: %(vertical_center)s,
				        mouseWheel: false,
				        fragments: true,
				        rollingLinks: false,
				        transition: '%(transition)s',
                                        transitionSpeed: 'fast',
                                        slideNumber: '',
                                        menu : {
                                          side: 'right',
                                          width: 'normal',
                                          numbers: false,
                                          titleSelector: 'h1, h2, h3, h4, h5, h6',
                                          useTextContentForMissingTitles: false,
                                          hideMissingTitles: false,
                                          markers: true,
                                          custom: false,
                                          themes: false,
                                          themesPath: 'css/theme/',
                                          transitions: false,
                                          openButton: true,
                                          openSlideNumber: false,
                                          keyboard: true,
                                          sticky: false,
                                          autoOpen: true,
                                          delayInit: false,
                                          openOnInit: false,
                                          loadIcons: true,
                                        },
      	keyboard: {
        37: 'prev', // right
      	39: 'next', // left
      	33: 'prev', // page up
      	34: 'next', // page down
      	38: 'prev', // page up
      	40: 'next', // page down
      	109: function() {Reveal.left(); Reveal.slide(Reveal.getIndices()['h'],0,0);}, // minus
      	107: function() {Reveal.right(); Reveal.slide(Reveal.getIndices()['h'],0,0);}, // plus
      	},
        dependencies: [
          { src: '%(rsttools_root)s/reveal-plugins/reveal.js-menu/menu.js', async: true },
          { src: '%(rsttools_root)s/reveal-plugins/toc-progress/toc-progress.js',
                async: true,
                callback: function()
                {
                    toc_progress.initialize(null,null,'{ background-color: white; color: black;}');
                    toc_progress.create();
                }
          }
          ]
        });

		        </script>"""

        footer += """
            %(script_page_number)s

	        %(footer)s
	        </body>
        </html>"""

        footer = footer % {'transition': self.settings['transition'],
                           'footer': self.footer_html,
                           'reveal_root': self.reveal_root,
                           'rstslide_root': self.rstslide_root,
                           'rsttools_root': self.rsttools_root,
                           'script_page_number': script_page_number,
                           'vertical_center': 'true' if self.settings['vertical_center'] else 'false',
                           'controls': 'true' if self.settings['controls'] else 'false'}

        return footer

    def _parse_docinfo(self, doctree, d=None):

        def getText(nodelist):
            # Iterate all Nodes aggregate TEXT_NODE
            rc = []
            for node in nodelist:
                if node.nodeType == node.TEXT_NODE:
                    rc.append(node.data)
                else:
                    # Recursive
                    rc.append(getText(node.childNodes))
            result = ''.join(rc)
            #for repl in template:
            #    result = result.replace('|'+repl+'|',template[repl])
            return result

        if d is None:
            d = {}

        #print(doctree)

        docdom = doctree.asdom()

        # Get all field lists in the document.
        docinfos = docdom.getElementsByTagName('docinfo')

        for docinfo in docinfos:
            for field in docinfo.childNodes:
                tag = field.tagName
                if tag == "authors":
                    authors = field.getElementsByTagName('author')
                    d["authors"] = [x.firstChild.nodeValue for x in authors]
                elif tag == "field":
                    field_name = field.getElementsByTagName('field_name')[0]
                    field_name_str = field_name.firstChild.nodeValue.lower()
                    field_body = field.getElementsByTagName('field_body')[0]
                    if field_name_str.endswith("-list"):
                        field_name = field_name_str[:-len("-list")]
                        if field_body.firstChild.tagName == 'bullet_list':
                            d[field_name] = [getText(x.childNodes) for x in field_body.childNodes] #[x.firstChild.firstChild.nodeValue % template for c in field_body.childNodes for x in c.childNodes]
                        else:
                            d[field_name] = [getText(field_body.childNodes)] #[getText(c.firstChild) % template for c in field_body.childNodes]
                    elif field_name_str.endswith("-list-add"):
                        field_name = field_name_str[:-len("-list-add")]
                        if not field_name in d:
                            d[field_name] = []
                        if field_body.firstChild.tagName == 'bullet_list':
                            d[field_name] += [getText(c.childNodes) for x in c.childNodes] #[x.firstChild.firstChild.nodeValue % template for c in field_body.childNodes for x in c.childNodes]
                        else:
                            d[field_name] += [getText(field_body.childNodes)] #[getText(c.firstChild) % template for c in field_body.childNodes]
                    else:
                        d[field_name_str] = getText(field_body.childNodes)#" ".join(getText(c.firstChild) for c in field_body.childNodes) % template

                else:
                    d[tag] = getText(field.childNodes) # % template

        topics = docdom.getElementsByTagName('topic')
        for topic in topics:
            classes = topic.getAttribute("classes").lower()
            if classes in [ 'abstract', 'dedication' ]:
                d[classes] = getText(topic.childNodes) #" ".join(getText(c.firstChild) for c in topic.childNodes)

        return d

    def _dict_to_rst_replacements(self,d):
        text = ''
        for key in d:
            try:
                out = ""+d[key]
            except TypeError:
                try:
                    out = "".join(d[key])
                except TypeError:
                    out = ""

            if out != '':
                out = out.replace('\n','\n  ').replace('*','\*')
                text += '.. |'+key+'| replace:: '+out+'\n\n'
            else:
                text += '.. |'+key+'| replace:: \ \n\n'
        return text

    def publish_parts_from_doctree(self, document, destination_path=None,
                                   writer=None, writer_name='pseudoxml',
                                   settings=None, settings_spec=None,
                                   settings_overrides=None, config_section=None,
                                   enable_exit_status=False):
        reader = docutils.readers.doctree.Reader(parser_name='null')
        pub = docutils.core.Publisher(reader, None, writer,
                        source=docutils.io.DocTreeInput(document),
                        destination_class=docutils.io.StringOutput, settings=settings)
        if not writer and writer_name:
            pub.set_writer(writer_name)
        pub.process_programmatic_settings(
            settings_spec, settings_overrides, config_section)
        pub.set_destination(None, destination_path)
        pub.publish(enable_exit_status=enable_exit_status)
        return pub.writer.parts

if __name__ == '__main__':
    # Create the object
    parser = Parser(input_file='index.rst')
    # Create the slides
    parser.create_slides()
