import re,sys
def load(fn='./dump/props.txt'):
    d={};cur=None
    for line in open(fn,encoding='utf-8',errors='replace'):
        if line.startswith('== '):
            m=re.match(r'== (.*) \[(\w+)\]$',line.rstrip('\n'))
            cur=m.group(1); d[cur]={'_class':m.group(2)}
        elif cur and line.startswith('    '):
            k,_,v=line.strip().partition(' = '); d[cur][k]=v
    return d
