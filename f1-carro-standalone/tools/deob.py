import re, sys
def lua_unescape(s):
    out=bytearray(); i=0
    esc={'n':10,'t':9,'r':13,'a':7,'b':8,'f':12,'v':11,'\\':92,'"':34,"'":39}
    while i<len(s):
        c=s[i]
        if c=='\\':
            n=s[i+1]
            if n.isdigit():
                m=re.match(r'\d{1,3}',s[i+1:]); out.append(int(m.group())); i+=1+len(m.group()); continue
            out.append(esc[n]); i+=2; continue
        out+=c.encode('utf-8'); i+=1
    return bytes(out)
def dec(s,k):
    s=lua_unescape(s); k=lua_unescape(k)
    return bytes(s[j] ^ k[(j+1)%len(k)] for j in range(len(s)))
src=open(sys.argv[1],encoding='utf-8').read()
pat=re.compile(r'v7\("((?:[^"\\]|\\.)*)",\s*"((?:[^"\\]|\\.)*)"\)')
def rep(m):
    d=dec(m.group(1),m.group(2)).decode('utf-8','replace')
    return '"'+d.replace('\\','\\\\').replace('"','\\"').replace('\n','\\n')+'"'
src=pat.sub(rep,src)
# fold simple constant arithmetic like (734.4 - (711 + 22)) repeatedly
num=r'-?\d+(?:\.\d+)?'
for _ in range(10):
    src2=re.sub(r'\(\s*('+num+r')\s*([-+])\s*('+num+r')\s*\)', lambda m: '('+repr(eval(m.group(0)))+')' if True else '', src)
    src2=re.sub(r'(?<=[(=,\[])(\s*)('+num+r')\s*([-+])\s*\((\s*'+num+r'\s*)\)(?=\s*[);,\]])', lambda m: m.group(1)+repr(eval(m.group(2)+m.group(3)+m.group(4))), src2)
    src2=re.sub(r'(?<=[(=,\[])(\s*)(\d+(?:\.\d+)?)\s*([-+])\s*(\d+(?:\.\d+)?)(?=\s*[);,\]])', lambda m: m.group(1)+repr(eval(m.group(2)+m.group(3)+m.group(4))), src2)
    src2=re.sub(r'\((\s*'+num+r'\s*)\)', r'\1', src2)
    if src2==src: break
    src=src2
open(sys.argv[2],'w').write(src)
