// Independent arithmetic oracle and instruction/edge-case checks.
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "i8008.hxx"

#define check(x) do { if ( !(x) ) { fprintf( stderr, "line %d: %s\n", __LINE__, #x ); exit( 1 ); } } while ( 0 )
static unsigned inputPort, outputPort, outputValue, reads, writes;
uint8_t i8008_input( uint8_t port ) { inputPort = port; reads++; return 0x96; }
void i8008_output( uint8_t port, uint8_t value ) { outputPort = port; outputValue = value; writes++; }
static I8008 cpu;
static bool g_bulk = false;
static unsigned instruction() { return g_bulk ? (unsigned) cpu.emulate( 1 ) : cpu.step(); }

static bool parity( unsigned value )
{
    unsigned ones = 0;
    for ( unsigned i = 0; i < 8; i++ )
        ones += ( value >> i ) & 1;
    return 0 == ( ones % 2 );
}

static void reset( unsigned opcode )
{
    cpu.power_on( 0x100 );
    memory[ 0x100 ] = (uint8_t) opcode;
    memory[ 0x101 ] = 0x78;
    memory[ 0x102 ] = 0xf6; // high two address bits must be ignored
    cpu.r[ 5 ] = 0xff;
    cpu.r[ 6 ] = 0xff;
    memory[ 0x3fff ] = 0x96;
    reads = writes = 0;
}

static void arithmetic()
{
    for ( unsigned operation = 0; operation < 8; operation++ )
    for ( unsigned a = 0; a < 256; a++ )
    for ( unsigned b = 0; b < 256; b++ )
    for ( unsigned carry = 0; carry < 2; carry++ )
    {
        int result = 0;
        switch ( operation )
        {
            case 0: result = a + b; break;
            case 1: result = a + b + carry; break;
            case 2: case 7: result = int( a ) - int( b ); break;
            case 3: result = int( a ) - int( b ) - int( carry ); break;
            case 4: result = a & b; break;
            case 5: result = a ^ b; break;
            case 6: result = a | b; break;
        }
        unsigned byte = result & 255;
        // Same operation through register, immediate and memory operands.
        for ( unsigned mode = 0; mode < 3; mode++ )
        {
            reset( mode == 0 ? 0x81 + operation * 8 : mode == 1 ? 4 + operation * 8 : 0x87 + operation * 8 );
            cpu.r[ 0 ] = (uint8_t) a;
            cpu.r[ 1 ] = memory[ 0x101 ] = memory[ 0x3fff ] = (uint8_t) b;
            cpu.fCarry = ( 0 != carry );
            check( instruction() == ( mode == 0 ? 10u : 16u ) );
            check( cpu.r[ 0 ] == ( operation == 7 ? a : byte ) );
            check( cpu.fCarry == ( result < 0 || result > 255 ) );
            check( cpu.fZero == ( byte == 0 ) );
            check( cpu.fSign == ( byte >= 128 ) );
            check( cpu.fParity == parity( byte ) );
        }
    }
}

static void decoding()
{
    for ( unsigned op = 0; op < 256; op++ )
    for ( unsigned flags = 0; flags < 16; flags++ )
    {
        reset( op );
        cpu.fCarry = flags & 1;
        cpu.fZero = flags & 2;
        cpu.fSign = flags & 4;
        cpu.fParity = flags & 8;
        unsigned group = ( op >> 3 ) & 7, low = op & 7;
        bool undefined = op < 0x40 && ( ( low <= 1 && group == 7 ) || ( low == 2 && group >= 4 ) );
        unsigned clocks = instruction();
        check( cpu.invalid == undefined );
        check( ( 0 == strcmp( cpu.render_operation( 0x100 ), "undefined" ) ) == undefined );
        check( cpu.halted == ( op == 0 || op == 1 || op == 255 ) );
        check( cpu.cycles == clocks );
        unsigned states = 5;
        if ( op == 0 || op == 1 || op == 255 ) states = 4;
        else if ( op >= 0xc0 ) states = low == 7 ? 8 : group == 7 ? 7 : 5;
        else if ( op >= 0x80 ) states = low == 7 ? 8 : 5;
        else if ( op >= 0x40 )
        {
            if ( op & 1 ) states = op < 0x51 ? 8 : 6;
            else
            {
                bool taken = ( op & 4 ) || ( bool( flags & ( 1 << ( group & 3 ) ) ) == bool( op & 0x20 ) );
                states = taken ? 11 : 9;
            }
        }
        else if ( low == 3 )
            states = bool( flags & ( 1 << ( group & 3 ) ) ) == bool( op & 0x20 ) ? 5 : 3;
        else if ( low == 4 ) states = 8;
        else if ( low == 6 ) states = group == 7 ? 9 : 8;
        check( clocks == states * 2 );
        if ( op >= 0x40 && op < 0x80 )
        {
            if ( op & 1 )
            {
                unsigned port = ( op - 0x41 ) / 2;
                check( clocks == ( port < 8 ? 16u : 12u ) );
                check( reads == ( port < 8 ? 1u : 0u ) );
                check( writes == ( port < 8 ? 0u : 1u ) );
                if ( port < 8 ) { check( inputPort == port ); check( cpu.r[ 0 ] == 0x96 ); }
                else { check( outputPort == port ); check( outputValue == 0 ); }
                check( cpu.pc() == 0x101 );
            }
            else
            {
                bool taken = ( op & 4 ) || ( bool( flags & ( 1 << ( group & 3 ) ) ) == bool( op & 0x20 ) );
                check( cpu.pc() == ( taken ? 0x3678 : 0x103 ) );
                check( cpu.sp == ( taken && ( op & 2 ) ? 1 : 0 ) );
                check( clocks == ( taken ? 22u : 18u ) );
                if ( taken && ( op & 2 ) ) check( cpu.stack[ 0 ] == 0x103 );
            }
        }
        else if ( op < 0x40 && low == 3 )
        {
            bool taken = bool( flags & ( 1 << ( group & 3 ) ) ) == bool( op & 0x20 );
            check( cpu.sp == ( taken ? 7 : 0 ) );
            check( clocks == ( taken ? 10u : 6u ) );
        }
        else if ( op < 0x40 && low == 7 ) { check( cpu.sp == 7 ); check( clocks == 10 ); }
        else if ( op < 0x40 && low == 5 )
        {
            check( cpu.sp == 1 ); check( cpu.pc() == ( op & 0x38 ) );
            check( cpu.stack[ 0 ] == 0x101 ); check( clocks == 10 );
        }
    }
}

static void transfers()
{
    for ( unsigned d = 0; d < 8; d++ )
    for ( unsigned s = 0; s < 8; s++ )
    {
        if ( d == 7 && s == 7 ) continue;
        reset( 0xc0 + d * 8 + s );
        for ( unsigned n = 0; n < 5; n++ ) cpu.r[ n ] = (uint8_t) ( 0x31 + n );
        uint8_t value = s == 7 ? memory[ 0x3fff ] : cpu.r[ s ];
        cpu.fCarry = cpu.fZero = cpu.fSign = cpu.fParity = true;
        check( instruction() == ( s == 7 ? 16u : d == 7 ? 14u : 10u ) );
        check( ( d == 7 ? memory[ 0x3fff ] : cpu.r[ d ] ) == value );
        check( cpu.fCarry && cpu.fZero && cpu.fSign && cpu.fParity );
    }
    for ( unsigned d = 0; d < 8; d++ )
    {
        reset( 6 + d * 8 );
        check( instruction() == ( d == 7 ? 18u : 16u ) );
        check( ( d == 7 ? memory[ 0x3fff ] : cpu.r[ d ] ) == 0x78 );
        check( cpu.pc() == 0x102 );
    }
}

static void increments_and_rotates()
{
    for ( unsigned value = 0; value < 256; value++ )
    for ( unsigned carry = 0; carry < 2; carry++ )
    {
        for ( unsigned reg = 1; reg <= 6; reg++ )
        for ( unsigned dec = 0; dec < 2; dec++ )
        {
            reset( reg * 8 + dec );
            cpu.r[ reg ] = (uint8_t) value;
            cpu.fCarry = carry;
            check( instruction() == 10 );
            unsigned result = ( value + ( dec ? -1 : 1 ) ) & 255;
            check( cpu.r[ reg ] == result );
            check( cpu.fCarry == bool( carry ) );
            check( cpu.fZero == ( result == 0 ) );
            check( cpu.fSign == ( result >= 128 ) );
            check( cpu.fParity == parity( result ) );
        }
        for ( unsigned rot = 0; rot < 4; rot++ )
        {
            reset( 2 + rot * 8 );
            cpu.r[ 0 ] = (uint8_t) value;
            cpu.fCarry = carry;
            cpu.fZero = cpu.fSign = cpu.fParity = true;
            unsigned out = rot % 2 ? value % 2 : value / 128;
            unsigned in = rot < 2 ? out : carry;
            unsigned result = rot % 2 ? value / 2 + 128 * in : ( value * 2 + in ) % 256;
            check( instruction() == 10 );
            check( cpu.r[ 0 ] == result ); check( cpu.fCarry == bool( out ) );
            check( cpu.fZero && cpu.fSign && cpu.fParity );
        }
    }
}

static void edges()
{
    reset( 0x46 ); // circular stack overwrites the oldest PC after eight calls
    for ( unsigned n = 0; n < 9; n++ )
    {
        memory[ cpu.pc() ] = 0x46;
        memory[ ( cpu.pc() + 1 ) & 0x3fff ] = 0x78;
        memory[ ( cpu.pc() + 2 ) & 0x3fff ] = 0x36;
        check( instruction() == 22 );
        check( cpu.sp == ( ( n + 1 ) & 7 ) );
        check( cpu.pc() == 0x3678 );
    }
    for ( unsigned n = 0; n < 9; n++ )
    {
        memory[ cpu.pc() ] = 7;
        instruction();
        check( cpu.sp == ( ( 8 - n ) & 7 ) );
    }
    cpu.power_on( 0x3fff );
    memory[ 0x3fff ] = 6; memory[ 0 ] = 0x42;
    check( instruction() == 16 ); check( cpu.r[ 0 ] == 0x42 ); check( cpu.pc() == 1 );
    cpu.power_on( 0x3ffe );
    memory[ 0x3ffe ] = 0x44; memory[ 0x3fff ] = 0x34; memory[ 0 ] = 0xd2;
    check( instruction() == 22 ); check( cpu.pc() == 0x1234 );
    reset( 0 );
    check( cpu.emulate( 1 ) == 8 ); check( cpu.emulate( 100 ) == 0 );
    check( cpu.interrupt( 0x15 ) == 10 ); check( cpu.pc() == 0x10 );
    check( cpu.stack[ 0 ] == 0x101 );
    memory[ 0x10 ] = 7;
    instruction(); check( cpu.pc() == 0x101 );
    // An emulated store must change the instruction fetched later in this batch.
    cpu.power_on( 0x100 );
    const uint8_t modifying[] = { 0x2e, 1, 0x36, 9, 0x3e, 0, 0x44, 9, 1, 6 };
    memcpy( memory + 0x100, modifying, sizeof( modifying ) );
    check( cpu.emulate( 1000 ) == 80 );
    check( memory[ 0x109 ] == 0 && cpu.halted && cpu.pc() == 0x10a );
    reset( 0xc0 );
    check( cpu.emulate( 0 ) == 0 );
    check( cpu.emulate( 9 ) == 10 );
    cpu.end_emulation(); check( cpu.emulate( 100 ) == 0 );
    check( cpu.pc() == 0x101 ); // stopped execution must not fetch
    cpu.ended = false; // public stop fields remain writable between calls
    memory[ cpu.pc() ] = 0xc0;
    check( cpu.emulate( 1 ) == 10 );
    reset( 0xc0 );
    cpu.cycles = UINT64_MAX - 5;
    check( cpu.emulate( 1 ) == 10 ); check( cpu.cycles == 4 );
    reset( 0xc0 );
    memory[ 0x101 ] = memory[ 0x102 ] = 0xc0;
    cpu.cycles = UINT64_MAX - 15;
    check( cpu.emulate( 19 ) == 20 ); check( cpu.cycles == 4 );
}

static void tracing( const char * path )
{
    CTrace tracer;
    check( tracer.Enable( true, path ) );
    reset( 6 );
    cpu.set_tracer( &tracer );
    cpu.trace_instructions( true );
    check( cpu.emulate( 1 ) == 16 );
    cpu.trace_instructions( false );
    memory[ cpu.pc() ] = 0xc0;
    check( instruction() == 10 ); // this LAA must not appear in the log
    cpu.trace_instructions( true );
    cpu.power_on( 0x3fff ); // preserve tracing configuration across reset
    memory[ 0x3fff ] = 0x44;
    memory[ 0 ] = 0x34;
    memory[ 1 ] = 0x12;
    check( 0 == strcmp( cpu.render_operation( 0x3fff ), "JMP 1234" ) );
    check( instruction() == 22 );
    memory[ 0x1234 ] = 0x78;
    memory[ 0x1235 ] = 0x16;
    check( cpu.interrupt( 0x46 ) == 22 );
    check( cpu.pc() == 0x1678 );
    cpu.trace_instructions( false );
    cpu.power_on( 0x3fff );
    memory[ 0x3fff ] = 0xff;
    check( instruction() == 8 );
    check( cpu.pc() == 0 );
    cpu.power_on( 0x2345 );
    check( cpu.interrupt( 0x22 ) == 10 );
    check( cpu.pc() == 0x2345 );
    cpu.power_on( 0x3456 );
    check( cpu.interrupt( 0x00 ) == 8 );
    check( cpu.pc() == 0x3456 );
    cpu.power_on( 0 );
    memory[ 0 ] = 0x3a;
    check( instruction() == 10 );
    cpu.set_tracer( 0 );
    cpu.trace_instructions( false );
    tracer.Shutdown();
    FILE * file = fopen( path, "r" );
    check( file );
    char text[ 4096 ];
    size_t count = fread( text, 1, sizeof( text ) - 1, file );
    text[ count ] = 0;
    fclose( file );
    check( strstr( text, "pc 0100, op 06, op2 78" ) );
    check( strstr( text, "cycles 0, LAI 78" ) );
    check( !strstr( text, "LAA" ) );
    check( strstr( text, "pc 3fff, op 44, op2 34, op3 12" ) );
    check( strstr( text, "JMP 1234" ) );
    check( strstr( text, "pc 1234, op 46, op2 78, op3 16" ) );
    check( strstr( text, "interrupt: CAL 1678" ) );
    check( strstr( text, "halt at 3fff, 8 cycles" ) );
    check( strstr( text, "undefined opcode at 2345, 10 cycles" ) );
    check( strstr( text, "halt at 3456, 8 cycles" ) );
    check( strstr( text, "undefined opcode at 0000, 10 cycles" ) );
}

int main( int argc, char * argv[] )
{
    // Run the same independent oracles through both public execution paths.
    for ( unsigned mode = 0; mode < 2; mode++ )
    {
        g_bulk = ( 0 != mode );
        arithmetic(); decoding(); transfers(); increments_and_rotates(); edges();
        if ( argc > 1 ) tracing( argv[ 1 ] );
    }
    puts( "CPU tests passed" );
}
