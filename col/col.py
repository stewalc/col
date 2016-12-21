#! /usr/bin/env python3
import os, sys, re, json
from queue import Queue
import queue
import threading
import collections
from collections import namedtuple
import imp
import functools
have_pygments=False
try:
    # from . import pygments
    imp.load_module('pygments', None, '{}/pygments/'.format(os.path.abspath(os.path.dirname(__file__))), ('','',5))
    have_pygments=True
except (ImportError, AttributeError):
    try:
        import pygments
        have_pygments=True
    except ImportError:
        pass
if have_pygments:
    import pygments.lexers
    import pygments.lexer
    import pygments.formatters
    from pygments.token import *

class Singleton(type):
    _instances = {}
    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances.keys(): cls._instances.update({cls:super(Singleton, cls).__call__(*args, **kwargs)})
        return cls._instances.get(cls)

class ComplexDecorator:
    def __init__(self, *args, **kwargs):
        self.ignore_exceptions=[]
        self.fn_exceptions={}
        self._update(*args, **kwargs)
    def __call__(self, func, *args, **kwargs):
        def wrap(*args, **kwargs):
            while True:
                try:
                    return func(*args, **kwargs)
                    break
                except Exception as e:
                    if type(e) in self.ignore_exceptions: continue
                    elif type(e) in self.fn_exceptions:
                        self.fn_exceptions[type(e)]()
                        continue
                    else: raise
        return wrap
    def _update(self, *args, **kwargs): self.__dict__.update(kwargs)

class SingletonBase(object):#, metaclass=Singleton):
    def __init__(self, *args, **kwargs): self(*args, **kwargs)
    def __call__(self, *args, **kwargs): self._update(*args, **kwargs)
    def __getattr__(self, name): return self.__dict__.get(name, None)
    def __str__(self): return '{} :: {}'.format(repr(self), self.__dict__)
    def _update(self, *args, **kwargs): self.__dict__.update(kwargs)

class ColorStream(SingletonBase):
    def __init__(self, *args, **kwargs):
        self._update(*args, **kwargs)
        super().__init__(*args, **kwargs)
        self._in_queue = Queue()
        self._out_queue = Queue()
        self._colorizers=[ColorizerFactory.get_colorizer(**clexer._asdict(), html_output=self.html_output) for clexer in self.clexers]
        self.clex=self.build_wrapper()
        if self.stream: self._handle_stream()

    @ComplexDecorator(ignore_exceptions=[queue.Empty])
    def _worker(self,in_q, out_q):
        while True:
            job=in_q.get_nowait()
            if job is None: break
            out_q.put( self.clex(job) )
        out_q.put(None)

    def build_wrapper(self):
        def wrap_func(func, prev_wrapper):
            def wrapper(*args): return func(prev_wrapper(*args))
            return wrapper
        wrapper=self._colorizers[0]
        for clex in self._colorizers[1:]: wrapper=wrap_func(clex,wrapper)
        return wrapper

    @ComplexDecorator(ignore_exceptions=[UnicodeDecodeError])
    def _populate_q(self):
        while True:
            item = self.stream.readline()
            if not item: break
            self._in_queue.put(item)
        self._in_queue.put(None)

    def _handle_stream(self):
        self._threads = [threading.Thread(target=self._worker, args=(self._in_queue, self._out_queue)),threading.Thread(target=self._populate_q)]
        [thread.start() for thread in self._threads]

class Obj:
    def __init__(self):self.end,self.output_text=0,''
    def update(self,*args):
        text,self.end=args
        self.output_text+=text

def NamedTuple(typename, field_names, default_values=()):
    T = collections.namedtuple(typename, field_names)
    T.__new__.__defaults__ = (None,) * len(T._fields)
    if isinstance(default_values, collections.Mapping): prototype = T(**default_values)
    else: prototype = T(*default_values)
    T.__new__.__defaults__ = tuple(prototype)
    return T

Clex=NamedTuple('Clex','pattern color style',{'pattern':'^(.*)$','color':'red','style':'normal'})
class ColorizerFactory(SingletonBase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
    @staticmethod
    def get_colorizer(pattern='^(.*)$', color='red', style='normal', html_output=False):
        class Colorizer:
            styles={kk:ii for ii,kk in enumerate(["normal","bold","faint","italic","underline","blink","rapid_blink","reverse","conceal"]) }
            colors={kk:ii-1 for ii,kk in enumerate(["none","black","red","green","yellow","blue","magenta","cyan","white"])}
            start,stop,endmarks = "\033[","\033[0m",{8: ";", 256: ";38;5;"}
            def __init__(self, *args, **kwargs):
                self._update(*args, **kwargs)
                self._setup()
            def _update(self, *args, **kwargs): self.__dict__.update(kwargs)
            def _setup(self):
                def gen_group(l_item, length): return l_item.split(',')+[l_item.split(',')[-1]]*(length-len(l_item.split(',')))
                self.regex = re.compile(self.pattern)
                self.group_colors,self.group_styles=[gen_group(item,self.regex.groups) for item in [self.color,self.style]]
                self.color_generator=self.gen_color()
                self.em=self.endmarks[8]
            def gen_color(self):
                for cc in self.group_colors: yield cc
            def reset_color_gen(self): self.color_generator=self.gen_color()
            def _color_it(self, text, match, end, group=0):
                @ComplexDecorator(fn_exceptions={StopIteration:self.reset_color_gen})
                def get_color():
                    if len(self.group_colors) > self.regex.groups: return next(self.color_generator)
                    else: return self.group_colors[[group,group-1][int(bool(group))]]
                color=get_color()
                style=self.group_styles[[group,group-1][int(bool(group))]]
                start = match.start(group)
                colored_text = text[end:start]
                end = match.end(group)
                colored_text += self.colorin(text[start:end], color, style)
                return colored_text, end
            def colorin(self,text, color, style):
                def get_color_code(color):
                    if color.isdigit(): return color
                    else: return str(30 + self.colors[color])
                def get_em(color):
                    if color.isdigit(): return self.endmarks[256]
                    else: return self.endmarks[8]
                c_dict={'text':text,'color_code':get_color_code(color),'style_code':str(self.styles.get(style,"")),'start':self.start,'stop':self.stop,'em':get_em(color)}
                return '{start}{style_code}{em}{color_code}m{text}{stop}'.format(**c_dict)
            def __call__(self, *args):
                if len(args)>1: return [self.__call__(arg) for arg in args]
                oo = Obj()
                def do_color(match):
                    if match.groups(): [oo.update(*self._color_it(args[0], match, oo.end,group_num)) for group_num in range(1,len(match.groups())+1)]
                    else: oo.update( *self._color_it(args[0],match,oo.end) )
                [ do_color(match) for match in self.regex.finditer(args[0])]
                return oo.output_text + args[0][oo.end:]
        tmp_col=Colorizer(pattern=pattern, color=color, style=style)
        if color in tmp_col.colors.keys() or color.replace(',','').replace(' ','').isdigit(): return tmp_col
        else:
            #if have_pygments: return functools.partial(pygments.highlight, lexer=CustomLexer(), formatter=pygments.formatters.Terminal256Formatter(style='monokai'))
            if have_pygments:
                formatter=pygments.formatters.Terminal256Formatter(style='monokai')
                if html_output:
                    formatter=pygments.formatters.HtmlFormatter(style='monokai')
                return functools.partial(pygments.highlight, lexer=pygments.lexers.get_lexer_by_name(color), formatter=formatter)
            else:
                raise Exception('Nothing found for color: {}'.format(color))

# class CustomLexer(pygments.lexer.RegexLexer):
#     name = 'custom'
#     aliases = ['custom']
#     filenames = ['*.*']
#     tokens = {
#         'root': [
#             (r'.*EntityType.*\n', Generic.Inserted),
#             (r' .*\n', Text),
#             (r'\+.*\n', Generic.Inserted),
#             (r'-.*\n', Generic.Deleted),
#             (r'@.*\n', Generic.Subheading),
#             (r'Index.*\n', Generic.Heading),
#             (r'=.*\n', Generic.Heading),
#             (r'.*\n', Text),
#         ]
#     }

class ColHandler(SingletonBase):
    def __init__(self, *args, **kwargs):
        self._update(*args, **kwargs)
        if self.json_config: self.__dict__.update({'config':json.load(open(self.json_config))})
        super().__init__(*args, **kwargs)
    def __call__(self, *args, **kwargs):
        if self.config:
            if self.color in self.config.keys(): self.clexers = [Clex(*ii) for ii in self.config[self.color].get('config',{})]
            if self.color in self.config.get('colormaps',{}).keys(): self.color = ','.join( (cc if type(cc)==str else str(cc)) for cc in self.config['colormaps'][self.color])
        if not self.clexers: self.clexers=[Clex((self.pattern if self.pattern else '^(.*)$'),(self.color if self.color else 'blue'),(self.style if self.style else 'bold'))]
        self._stream = ColorStream(stream=(open(self.filename) if self.filename else sys.stdin), clexers=self.clexers, html_output=self.html_output)
        self._handle_outstream()

    def _handle_outstream(self):
        while True:
            job=self._stream._out_queue.get()
            if job is None: return
            else: print(job, end='')

def _opt_parse(usage=''):
    import optparse
    opt_list=[(('-p','--pattern'),{'dest':'pattern','default':'^(.*)$','help':'A regular expression'}),
              (('-c','--color'),{'dest':'color', 'default':'red', 'help':'A Color'}),
              (('-t','--as-theme'),{'dest':'as_theme', 'action':'store_true'}),
              (('-j','--json-config'),{'dest':'json_config','help':'JSON format configuration file'}),
              (('-d','--debug'),{'dest':'debug', 'action':'store_true'}),
              (('-f', '--filename'),{'dest':'filename', 'default':None}),
              (('-m','--html-output'),{'dest':'html_output', 'action':'store_true'})
            ]
    parser=optparse.OptionParser(description=usage, option_list=[optparse.Option(*ii[0],**ii[1]) for ii in opt_list])
    values, arguments=parser.parse_args()
    return values.__dict__, arguments

def main():
    options, arguments = _opt_parse()
    ch=ColHandler(**options)

if __name__=="__main__":
    main()
