import struct, zstandard, sys
sys.path.insert(0,'.')
def hull_vertices(path):
    d=open(path,'rb').read(); assert d[:6]==b'CSGPHS'
    raw=zstandard.ZstdDecompressor().decompress(d[12:], max_output_size=50_000_000)
    h=struct.unpack('<9i',raw[:36]); nh,nv,nt=h[0],h[1],h[2]; asz,vsz=h[7],h[8]
    bb=struct.unpack('<6f',raw[36:60])
    assert vsz==nv*12 and 60+asz+vsz==len(raw), (h,len(raw))
    off=60+asz
    V=[struct.unpack('<3f',raw[off+12*i:off+12*i+12]) for i in range(nv)]
    return h,bb,V
