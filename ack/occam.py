#!/usr/bin/env python3
"""Compile sequential ACK Occam 1 programs to native 8008 Intel HEX."""
import argparse
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from codegen import CodegenError, generate
from compile import ROOT, HERE, TOOLS, SUFFIX, run, compile_c_unit
from wirth import trim_runtime, lower_fixed_arrays
from occam_storage import static_workspaces


def normalize(program):
    # Occam emits the frame size at END, leaving PRO's operand unspecified.
    def procedure(match):
        text=match[0]
        size=int(re.search(r'^ end (\d+)',text,re.M)[1])
        if re.search(r'^ dup 4$',text,re.M):
            a,b=-size-2,-size-4
            replacement=f' stl {a}\n stl {b}\n lol {b}\n lol {a}\n lol {b}\n lol {a}'
            text=re.sub(r'^ dup 4$',replacement,text,flags=re.M)
            size+=4
            text=re.sub(r'^ end \d+',f' end {size}',text,flags=re.M)
        return re.sub(r'^( pro [^,]+),(?:\?|\d+)',lambda m:m[1]+','+str(size),text,flags=re.M)
    program=re.sub(r'^ ldl (-?\d+)$',lambda m:f' lol {int(m[1])+2}\n lol {m[1]}',program,flags=re.M)
    program=re.sub(r'^ sdl (-?\d+)$',lambda m:f' stl {m[1]}\n stl {int(m[1])+2}',program,flags=re.M)
    program=re.sub(r'^ blm (\d+)$',lambda m:' loc '+m[1]+'\n cal $occam_copy\n asp 6',program,flags=re.M)
    program=re.sub(r'^ trp ?$', ' cal $occam_trap\n asp 2',program,flags=re.M)
    program=re.sub(r'^ lor 0$', ' lxl 0',program,flags=re.M)
    return re.sub(r'^ pro [^\n]+\n.*?^ end \d+',procedure,program,flags=re.M|re.S)


def lower_arrays(program):
    # These descriptors have fixed zero lower bounds and element widths. Their
    # mutable upper field is unused with the unchecked array ABI, as in the
    # Pascal/Modula-2 integrations. Preserve address/index evaluation order.
    program=re.sub(r'^ loc \d+\n ste (?:worddes|bytedes|chandes)\+2\n','',program,flags=re.M)
    def access(match):
        name,operation=match.groups()
        size={'worddes':2,'bytedes':1,'chandes':4}[name]
        result=(' loc '+str(size)+'\n mlu 2\n' if size!=1 else '')+' ads 2'
        if operation=='lar':result+='\n loi '+str(size)
        return result
    program=re.sub(r'^ lae (worddes|bytedes)\n (aar|lar) 2$',access,program,flags=re.M)
    return lower_fixed_arrays(program)


def compile_source(source, *, optimize_arrays=True, workspace='auto'):
    if workspace not in ('auto','all','main','stack'):
        raise CodegenError('invalid Occam workspace mode')
    for tool in ('em_occam','cpp.ansi','em_cemcom.ansi','em_opt','em_decode'):
        if not (TOOLS/(tool+SUFFIX)).is_file():
            raise CodegenError('ACK Occam tools not built; run ack/build.sh')
    with tempfile.TemporaryDirectory(prefix='ACK Occam ') as directory:
        work=Path(directory)
        text=(HERE/'occam/console.ocm').read_text()+'\n'+Path(source).read_text()
        compact=run([TOOLS/('em_occam'+SUFFIX),'-Vw2p2l2','-L'],input=text.encode('ascii'),cwd=work)
        (work/'program.k').write_bytes(run([TOOLS/('em_opt'+SUFFIX)],input=compact))
        run([TOOLS/('em_decode'+SUFFIX),work/'program.k',work/'program.e'])
        program=normalize((work/'program.e').read_text())
        procedures=set(re.findall(r'^ pro (\$[^,]+)',program,re.M))
        allowed={'$init','$chan_out','$chan_in','$cbyte_in','$c_ba_out','$c_wa_out',
                 '$c_ba_in','$c_wa_in','$b_exit','$occam_trap','$occam_copy'}
        unsupported=set(re.findall(r'^ cal (\S+)',program,re.M))-procedures-allowed
        if unsupported:
            raise CodegenError('unsupported Occam runtime operation: '+', '.join(sorted(unsupported)))
        support=[compile_c_unit(HERE/'occam/runtime.c',work,'runtime'),
                 compile_c_unit(HERE/'pascal/runtime.c',work,'arrays'),
                 compile_c_unit(HERE/'console.c',work,'console')]
        modes=('all','main','stack') if workspace=='auto' else (workspace,)
        last_error=None
        for mode in modes:
            candidate=static_workspaces(program,mode)
            if optimize_arrays:candidate=lower_arrays(candidate)
            units=[candidate,*trim_runtime(candidate,support)]
            # Avoid assembling definitely oversized static arenas before
            # trying the stack fallback, where separate procedures reuse RAM.
            if mode!='stack' and sum(map(int,re.findall(r'^ bss (\d+),',candidate,re.M)))>0x3c00:
                last_error=CodegenError('static workspace leaves insufficient RAM for stack')
                continue
            assembly=generate(units,pascal=True)
            (work/'program.asm').write_bytes(assembly.encode('ascii'))
            run([ROOT/'a08'/('a08'+SUFFIX),work/'program.asm','-o'+str(work/'program.hex')])
            image=(work/'program.hex').read_text()
            end=max(int(line[3:7],16)+int(line[1:3],16) for line in image.splitlines() if line[7:9]=='00')
            main=re.search(r'^ pro \$main,(\d+)$',candidate,re.M)
            frame=int(main[1]) if main else 0
            floor=(end+255)&~255 if mode!='stack' else end
            if floor+frame+512>0x3f00:
                last_error=CodegenError('code/data and main frame leave less than 512 bytes of stack')
                continue
            if end>0x3d00:
                last_error=CodegenError('code/data exceed 15616 bytes; at least 512 bytes of stack required')
                continue
            return image,assembly,'\n'.join(units)
        raise last_error



def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source',type=Path)
    parser.add_argument('-o','--output',type=Path)
    parser.add_argument('--assembly',type=Path)
    parser.add_argument('--em',type=Path)
    parser.add_argument('--workspace',choices=('auto','all','main','stack'),default='auto',
                        help='prefer safe static workspaces, falling back to stack when needed')
    args=parser.parse_args()
    try:
        image,assembly,em=compile_source(args.source,workspace=args.workspace)
        for destination,text in ((args.output or args.source.with_suffix('.hex'),image),
                                 (args.assembly,assembly),(args.em,em)):
            if destination:destination.write_bytes(text.encode('ascii'))
        print(f'{args.source}: compiled to {args.output or args.source.with_suffix(".hex")}')
    except (OSError,ValueError,subprocess.TimeoutExpired) as error:
        parser.exit(1,'ACK Occam/8008: '+str(error)+'\n')


if __name__=='__main__':main()
