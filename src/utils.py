from configparser import ConfigParser
import re
import ast

def readProperties(conf,file,section):
    '''
    Reads each property from the config file
    Input: 
        conf: dictionary where key-values will be mapped
        file: path and name of properties file
    Output: by reference in dictionary
    '''
    config = ConfigParser(inline_comment_prefixes='#')
    config.read(file)

    floatExp = re.compile('^[-+]?[0-9]+\.[0-9]+$')
    sciExp = re.compile('[+\-]?[^A-Za-z]?(?:0|[1-9]\d*)(?:\.\d*)?(?:[eE][+\-]?\d+)')
    intExp = re.compile('^[-+]?[0-9]+$')
    listExp = re.compile('^\[(\d+,\s*)+\d+\]$')
    listTuplesExp = re.compile('^\[\(\d+, \d+\)\]$')

    #Find each property in the specified section
    try:
        props = config[section]
    except:
        raise ValueError('Section {} does not exist'.format(section))
    for key in props:
        if floatExp.match(config[section][key]) != None or sciExp.match(config[section][key]) != None:
            conf[key] = float(config[section][key])
        elif intExp.match(config[section][key]):
            conf[key] = int(config[section][key])
        elif listExp.match(config[section][key]):
            conf[key] = ast.literal_eval(config[section][key])
        #elif listTuplesExp.match(config[section][key]):
        else:
            try:
                conf[key] = ast.literal_eval(config[section][key])
            except:
                raise ValueError('Only integers, floats and lists are allowed as properties, invalid value in {}'.format(key))
        #else:
            #raise ValueError('Only integers, floats and lists are allowed as properties, invalid value in {}'.format(key))


