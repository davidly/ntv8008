#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <chrono>
#include <fstream>
#include <string>
#include "i8008.hxx"

static I8008 cpu;
static CTrace tracer;
static uint8_t initial[16384];
static std::string input;
static size_t position;
static uint64_t outputHash;
uint8_t i8008_input( uint8_t port )
{
    if ( port == 1 ) return position < input.size() ? 0x80 : 0;
    if ( port != 2 ) return 0xff;
    if ( position == input.size() ) { cpu.end_emulation(); return 0xff; }
    uint8_t ch = (uint8_t) input[position++];
    return ( ch == '\n' ? '\r' : ch ) | 0x80;
}
void i8008_output( uint8_t port, uint8_t value )
{
    if ( port == 10 ) outputHash = outputHash * 131 + ( value & 127 );
}
int main( int argc, char ** argv )
{
    if ( argc < 2 ) return 1;
    std::ifstream hex(argv[1]);
    if ( !hex ) return 2;
    std::string line;
    while ( std::getline(hex,line) )
    {
        if ( line.size() < 11 || line[0] != ':' ) return 3;
        unsigned length, address, type;
        if ( sscanf(line.c_str()+1,"%2x%4x%2x",&length,&address,&type) != 3 ) return 3;
        if ( type != 0 ) continue;
        if ( address + length > 16384 || line.size() < 11 + length*2 ) return 3;
        unsigned sum = length + (address>>8) + (address&255) + type;
        for ( unsigned i=0; i<=length; i++ )
        {
            unsigned byte;
            if ( sscanf(line.c_str()+9+i*2,"%2x",&byte) != 1 ) return 3;
            sum += byte;
            if ( i<length ) initial[address+i]=(uint8_t)byte;
        }
        if ( sum & 255 ) return 3;
    }
    if ( argc>2 )
    {
        std::ifstream source(argv[2],std::ios::binary);
        if ( !source ) return 4;
        input.assign(std::istreambuf_iterator<char>(source), std::istreambuf_iterator<char>());
    }
    tracer.Enable( argc > 3, argc > 3 ? argv[3] : "unused.log" );
    cpu.set_tracer( &tracer );
    const auto start=std::chrono::steady_clock::now();
    unsigned runs=0;
    double elapsed=0;
    uint64_t expectedCycles=0, expectedHash=0;
    do
    {
        memcpy(memory,initial,sizeof(initial));
        cpu.power_on(0x40);
        position=0;outputHash=0;
        cpu.emulate(2000000000ULL);
        if ( !cpu.halted && !cpu.ended ) return 5;
        if ( !runs ) { expectedCycles=cpu.cycles; expectedHash=outputHash; }
        if ( cpu.cycles!=expectedCycles || outputHash!=expectedHash ) return 6;
        runs++;
        elapsed=std::chrono::duration<double>(std::chrono::steady_clock::now()-start).count();
    } while ( elapsed < 0.20 );
    printf("%u %.9f %llu %llu\n",runs,elapsed,(unsigned long long)expectedCycles,(unsigned long long)expectedHash);
}
