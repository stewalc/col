# col
Colorize text streams

I liked [colout](http://github.com/nojhan/colout) and wanted to rewrite it for some of my own utilities.

**pygments** module is optional, but very helpful.

The regex colorizers are defined in a JSON config file (example given at `config/config.json`)

## Usage:
Command-line flag driven:
`python3 col/col.py -j config/config.json -f config/config.json -c json`

Or via Pipes:
`cat config/config.json | python3 col/col.py -j config/config.json -c json`

### Help:
```
Usage: col.py [options]

Options:
  -p PATTERN, --pattern=PATTERN
                        A regular expression
  -c COLOR, --color=COLOR
                        A Color
  -t, --as-theme        
  -j JSON_CONFIG, --json-config=JSON_CONFIG
                        JSON format configuration file
  -d, --debug           
  -f FILENAME, --filename=FILENAME
  -m, --html-output     
  -h, --help            show this help message and exit
  ```

