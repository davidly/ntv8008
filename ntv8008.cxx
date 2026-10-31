// Console host for the Intel 8008. Build with i8008.cxx (C++11 or later).
// Windows: cl /EHsc /O2 ntv8008.cxx i8008.cxx
// Linux/macOS: c++ -std=c++11 -O2 ntv8008.cxx i8008.cxx -o ntv8008

#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <errno.h>
#include <ctype.h>
#include <signal.h>
#include <chrono>
#include <thread>
#include <fstream>
#include <string>
#include <vector>
#ifdef _WIN32
#include <conio.h>
#include <io.h>
#else
#include <unistd.h>
#include <termios.h>
#endif
#include "i8008.hxx"

// Original 1972 8008 clock. Cycle counts already include two clocks per T state.
static const unsigned g_originalClockHz = 500000;
static I8008 cpu;
static CTrace tracer;
static FILE * g_input = stdin;
static volatile sig_atomic_t g_stopped = 0;
static bool g_eof = false;
static unsigned g_inputPort = 2, g_outputPort = 10; // octal 12

static void on_signal( int ) { g_stopped = 1; }

class ConsoleConfiguration
{
#ifndef _WIN32
    termios saved;
    bool changed;
#endif
public:
    ConsoleConfiguration()
    {
#ifndef _WIN32
        changed = false;
        if ( stdin == g_input && isatty( STDIN_FILENO ) && 0 == tcgetattr( STDIN_FILENO, &saved ) )
        {
            termios raw = saved;
            raw.c_lflag &= ~( ICANON | ECHO );
            raw.c_iflag &= ~( ICRNL | INLCR );
            raw.c_cc[ VMIN ] = 1;
            raw.c_cc[ VTIME ] = 0;
            changed = ( 0 == tcsetattr( STDIN_FILENO, TCSANOW, &raw ) );
        }
#endif
    }
    ~ConsoleConfiguration()
    {
#ifndef _WIN32
        if ( changed )
            tcsetattr( STDIN_FILENO, TCSANOW, &saved );
#endif
    }
}; //ConsoleConfiguration

uint8_t i8008_input( uint8_t port )
{
    if ( port != g_inputPort )
    {
        tracer.Trace( "input port %u unmapped, returning ff\n", port );
        return 0xff;
    }
    int ch;
#ifdef _WIN32
    if ( stdin == g_input && _isatty( _fileno( stdin ) ) )
    {
        while ( !_kbhit() && !g_stopped )
            std::this_thread::sleep_for( std::chrono::milliseconds( 1 ) );
        ch = g_stopped ? EOF : _getch();
        if ( 0 == ch || 0xe0 == ch )
        {
            _getch();
            return 0xff;
        }
    }
    else
#endif
        ch = fgetc( g_input );
    if ( EOF == ch || 3 == ch || 17 == ch )
    {
        g_eof = ( EOF == ch );
        tracer.Trace( "keyboard %s; ending emulation\n", g_eof ? "EOF" : "exit key" );
        cpu.end_emulation();
        return 0xff;
    }
    if ( '\n' == ch )
        ch = '\r';
    tracer.Trace( "input port %u, character %02x, returning %02x\n", port, ch, ( ch & 0x7f ) | 0x80 );
    return (uint8_t) ( ( ch & 0x7f ) | 0x80 ); // bit 7 indicates a ready character
} //i8008_input

void i8008_output( uint8_t port, uint8_t value )
{
    tracer.Trace( "output port %u, value %02x%s\n", port, value, port != g_outputPort ? " (unmapped)" : "" );
    if ( port != g_outputPort )
        return;
    value &= 0x7f;
    putchar( '\r' == value ? '\n' : value );
    fflush( stdout );
} //i8008_output

static bool load_hex( const char * path )
{
    std::ifstream file( path );
    if ( !file )
    {
        fprintf( stderr, "can't open %s\n", path );
        return false;
    }
    std::string line;
    unsigned lineno = 0;
    uint32_t base = 0;
    bool eof = false, data = false;
    while ( std::getline( file, line ) )
    {
        lineno++;
        if ( !line.empty() && '\r' == line.back() )
            line.pop_back();
        if ( line.empty() )
            continue;
        uint8_t bytes[ 260 ];
        bool valid = !eof && ':' == line[ 0 ] && line.size() >= 11 && 1 == ( line.size() & 1 );
        unsigned count = 0, sum = 0;
        if ( valid )
        {
            for ( size_t i = 1; i < line.size(); i += 2 )
            {
                unsigned value = 0;
                for ( size_t j = i; j < i + 2; j++ )
                {
                    int ch = toupper( (unsigned char) line[ j ] );
                    if ( ch >= '0' && ch <= '9' ) ch -= '0';
                    else if ( ch >= 'A' && ch <= 'F' ) ch -= 'A' - 10;
                    else { valid = false; break; }
                    value = ( value << 4 ) | ch;
                }
                if ( !valid || count == sizeof( bytes ) ) { valid = false; break; }
                bytes[ count++ ] = (uint8_t) value;
                sum += value;
            }
            valid = valid && count == unsigned( bytes[ 0 ] ) + 5 && 0 == ( sum & 255 );
        }
        if ( valid )
        {
            unsigned length = bytes[ 0 ], address = ( bytes[ 1 ] << 8 ) | bytes[ 2 ], type = bytes[ 3 ];
            if ( 0 == type )
            {
                valid = base + address <= sizeof( memory ) && length <= sizeof( memory ) - ( base + address );
                if ( valid && length )
                {
                    memcpy( memory + base + address, bytes + 4, length );
                    data = true;
                }
            }
            else if ( 1 == type )
            {
                // A08 writes its final PC in the EOF address field.
                valid = ( 0 == length );
                eof = valid;
            }
            else if ( 2 == type || 4 == type )
            {
                valid = ( 2 == length && 0 == address );
                if ( valid )
                    base = uint32_t( ( bytes[ 4 ] << 8 ) | bytes[ 5 ] ) << ( 2 == type ? 4 : 16 );
            }
            else
                valid = false;
        }
        if ( !valid )
        {
            fprintf( stderr, "%s:%u: invalid, unsupported, or out-of-range Intel HEX record\n", path, lineno );
            return false;
        }
    }
    if ( file.bad() || !eof || !data )
    {
        fprintf( stderr, "%s: incomplete or empty Intel HEX file\n", path );
        return false;
    }
    tracer.Trace( "loaded HEX file %s\n", path );
    return true;
} //load_hex

static void usage()
{
    printf( "Intel 8008 console machine\n"
            "usage: ntv8008 [options] file.hex [more.hex ...]\n"
            "  -a:address  entry address (default 0x40)\n"
            "  -l:file     read keyboard input from a file (EOF exits)\n"
            "  -n:cycles   stop after at least this many clock periods; failure if not halted\n"
            "  -s:Hz       limit speed in clock periods/second (e.g. 500000)\n"
            "  -p          report cycles, elapsed time, and estimated 500 kHz 8008 runtime\n"
            "  -t          enable debug tracing to ntv8008.log (overwrites previous log)\n"
            "  -i          include each instruction in the log; requires -t\n"
            "  --in:port   keyboard port, 0..7 (default 2)\n"
            "  --out:port  console port, 8..31 (default 10 decimal)\n"
            "Numbers use decimal, 0x hex, or leading-zero octal.\n"
            "Console: 7-bit characters, LF input becomes CR, CR output becomes LF.\n"
            "Ctrl-C or Ctrl-Q exits. Redirected stdin is supported. HLT exits successfully.\n" );
} //usage

static bool number( const char * text, uint64_t & value )
{
    if ( !*text || '-' == *text || isspace( (unsigned char) *text ) )
        return false;
    char * end;
    errno = 0;
    value = strtoull( text, &end, 0 );
    return !errno && !*end;
} //number

int main( int argc, char * argv[] )
{
    uint64_t address = 0x40, limit = 0, hz = 0;
    bool performance = false, trace = false, traceInstructions = false, options = true;
    std::vector< const char * > files;
    const char * inputPath = 0;
    for ( int i = 1; i < argc; i++ )
    {
        const char * arg = argv[ i ];
        uint64_t value = 0;
        if ( options && 0 == strcmp( arg, "--" ) ) { options = false; continue; }
        if ( options && ( 0 == strcmp( arg, "--help" ) || 0 == strcmp( arg, "-h" ) ) ) { usage(); return 0; }
        if ( options && 0 == strcmp( arg, "-p" ) ) performance = true;
        else if ( options && 0 == strcmp( arg, "-t" ) ) trace = true;
        else if ( options && 0 == strcmp( arg, "-i" ) ) traceInstructions = true;
        else if ( options && 0 == strncmp( arg, "-l:", 3 ) && arg[ 3 ] ) inputPath = arg + 3;
        else if ( options && '-' == *arg )
        {
            const char * colon = strchr( arg, ':' );
            bool valid = colon && number( colon + 1, value );
            if ( valid && 0 == strncmp( arg, "-a:", 3 ) && value < 16384 ) address = value;
            else if ( valid && 0 == strncmp( arg, "-n:", 3 ) && value ) limit = value;
            else if ( valid && 0 == strncmp( arg, "-s:", 3 ) && value ) hz = value;
            else if ( valid && 0 == strncmp( arg, "--in:", 5 ) && value < 8 ) g_inputPort = (unsigned) value;
            else if ( valid && 0 == strncmp( arg, "--out:", 6 ) && value >= 8 && value < 32 ) g_outputPort = (unsigned) value;
            else { fprintf( stderr, "invalid option: %s\n", arg ); return 1; }
        }
        else
        {
            files.push_back( arg );
        }
    }
    if ( files.empty() ) { usage(); return 1; }
    if ( !tracer.Enable( trace, "ntv8008.log", true ) )
    {
        fprintf( stderr, "can't create ntv8008.log\n" );
        return 1;
    }
    cpu.set_tracer( &tracer );
    cpu.trace_instructions( traceInstructions );
    tracer.Trace( "Intel 8008 console, entry %04x, input port %u, output port %u, limit %llu, Hz %llu\n",
                  (unsigned) address, g_inputPort, g_outputPort, (unsigned long long) limit, (unsigned long long) hz );
    for ( size_t i = 0; i < files.size(); i++ )
    {
        if ( !load_hex( files[ i ] ) )
        {
            tracer.Trace( "failed to load HEX file %s\n", files[ i ] );
            return 1;
        }
    }
    if ( inputPath )
    {
        g_input = fopen( inputPath, "rb" );
        if ( !g_input )
        {
            tracer.Trace( "can't open keyboard input file %s\n", inputPath );
            fprintf( stderr, "can't open %s\n", inputPath );
            return 1;
        }
        tracer.Trace( "keyboard input file %s\n", inputPath );
    }
    ConsoleConfiguration console;
#ifdef _WIN32
    signal( SIGINT, on_signal );
    signal( SIGTERM, on_signal );
#else
    struct sigaction action = {};
    action.sa_handler = on_signal;
    sigemptyset( &action.sa_mask );
    sigaction( SIGINT, &action, 0 ); // interrupt a blocked keyboard read, too
    sigaction( SIGTERM, &action, 0 );
#endif
    cpu.power_on( (uint16_t) address );
    auto start = std::chrono::steady_clock::now();
    while ( !cpu.halted && !cpu.ended && !g_stopped && ( !limit || cpu.cycles < limit ) )
    {
        // Keep throttled runs responsive to their speed target. Unthrottled
        // runs can amortize host-loop overhead over a larger CPU batch.
        uint64_t budget = hz ? 1024 : 65536;
        if ( limit && limit - cpu.cycles < budget )
            budget = limit - cpu.cycles;
        cpu.emulate( budget );
        if ( hz )
            std::this_thread::sleep_until( start + std::chrono::duration_cast< std::chrono::steady_clock::duration >(
                std::chrono::duration<double>( double( cpu.cycles ) / double( hz ) ) ) );
    }
    tracer.Trace( "execution ended: %s, pc %04x, %llu cycles\n",
                  cpu.invalid ? "undefined opcode" : cpu.halted ? "halt" : g_stopped ? "signal" :
                  g_eof ? "input EOF" : cpu.ended ? "host exit" : "cycle limit", cpu.pc(), (unsigned long long) cpu.cycles );
    if ( performance )
    {
        fprintf( stderr, "%llu cycles, %.6f seconds elapsed%s\n", (unsigned long long) cpu.cycles,
                 std::chrono::duration<double>( std::chrono::steady_clock::now() - start ).count(), g_eof ? " (input EOF)" : "" );
        fprintf( stderr, "approximate real 8008 runtime: %.6f seconds at %u Hz (500 kHz; excluding I/O waits)\n",
                 double( cpu.cycles ) / g_originalClockHz, g_originalClockHz );
    }
    if ( stdin != g_input ) fclose( g_input );
    if ( cpu.invalid ) { fprintf( stderr, "undefined opcode at %04x\n", ( cpu.pc() - 1 ) & 0x3fff ); return 1; }
    if ( limit && cpu.cycles >= limit && !cpu.halted && !cpu.ended && !g_stopped )
    {
        fprintf( stderr, "cycle limit reached at %04x\n", cpu.pc() );
        return 2;
    }
    return g_stopped ? 130 : 0;
} //main
