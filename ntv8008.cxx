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
#include <map>
#include <sstream>
#ifdef _WIN32
#define NOMINMAX
#include <windows.h>
#include <conio.h>
#include <io.h>
#include <fcntl.h>
#else
#include <unistd.h>
#include <termios.h>
#include <poll.h>
#endif
#include "i8008.hxx"

// Original 1972 8008 clock. Cycle counts already include two clocks per T state.
static const unsigned g_originalClockHz = 500000;
static I8008 cpu;
static CTrace tracer;
static FILE * g_input = stdin;
static volatile sig_atomic_t g_stopped = 0;
static bool g_eof = false;
static int g_pendingInput = -1;
static bool g_inputEof = false;
static unsigned g_statusPort = 1;
static unsigned g_inputPort = 2, g_outputPort = 10; // octal 12

// Map addresses are hexadecimal, independent of command-line number syntax.
static std::map< uint16_t, std::string > g_symbols;

static const char * symbol_lookup( uint16_t address, uint16_t & offset )
{
    auto found = g_symbols.upper_bound( address );
    if ( found == g_symbols.begin() ) return 0;
    --found;
    offset = address - found->first;
    return found->second.c_str();
} //symbol_lookup

static bool load_symbols( const char * path )
{
    std::ifstream input( path );
    if ( !input ) { fprintf( stderr, "can't open symbol map: %s\n", path ); return false; }
    std::string line;
    unsigned lineNumber = 0;
    while ( std::getline( input, line ) )
    {
        lineNumber++;
        std::istringstream fields( line );
        std::string address, name, extra;
        if ( !( fields >> address ) || '#' == address[ 0 ] ) continue;
        char * end;
        errno = 0;
        unsigned long value = strtoul( address.c_str(), &end, 16 );
        if ( errno || *end || end == address.c_str() || value >= 16384 ||
             !( fields >> name ) || ( fields >> extra ) || g_symbols.count( (uint16_t) value ) )
        {
            fprintf( stderr, "invalid symbol map %s, line %u\n", path, lineNumber );
            return false;
        }
        g_symbols[ (uint16_t) value ] = name;
    }
    return !input.bad();
} //load_symbols

static void on_signal( int ) { g_stopped = 1; }

class ConsoleConfiguration
{
#ifdef _WIN32
    HANDLE output;
    DWORD saved;
    bool changed;
#else
    termios saved;
    bool changed;
#endif
public:
    ConsoleConfiguration()
    {
#ifdef _WIN32
        output = GetStdHandle( STD_OUTPUT_HANDLE );
        changed = GetConsoleMode( output, &saved ) &&
            SetConsoleMode( output, saved | ENABLE_PROCESSED_OUTPUT | ENABLE_VIRTUAL_TERMINAL_PROCESSING );
#else
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
#ifdef _WIN32
        if ( changed )
            SetConsoleMode( output, saved );
#else
        if ( changed )
            tcsetattr( STDIN_FILENO, TCSANOW, &saved );
#endif
    }
}; //ConsoleConfiguration

static int read_character()
{
#ifdef _WIN32
    // Even unbuffered Windows stdio can retain a second byte. Read exactly one
    // byte through the CRT descriptor so PeekNamedPipe sees everything else.
    unsigned char ch;
    return 1 == _read( _fileno( g_input ), &ch, 1 ) ? ch : EOF;
#else
    return fgetc( g_input );
#endif
} //read_character

// A status read never waits, consumes a character, or ends the emulation at EOF.
// One-byte lookahead also works for redirected files and pipes. Disable stdio
// read-ahead so a descriptor's readiness always reflects its remaining bytes.
static bool keyboard_ready()
{
    if ( g_pendingInput >= 0 )
        return true;
    if ( g_inputEof )
        return false;
#ifdef _WIN32
    if ( stdin == g_input && _isatty( _fileno( stdin ) ) )
        return 0 != _kbhit();
    HANDLE input = (HANDLE) _get_osfhandle( _fileno( g_input ) );
    if ( FILE_TYPE_PIPE == GetFileType( input ) )
    {
        DWORD available = 0;
        if ( !PeekNamedPipe( input, 0, 0, 0, &available, 0 ) || !available )
            return false;
    }
    else if ( FILE_TYPE_DISK != GetFileType( input ) )
        return false;
#else
    pollfd input = { fileno( g_input ), POLLIN, 0 };
    if ( poll( &input, 1, 0 ) <= 0 || !( input.revents & ( POLLIN | POLLHUP ) ) )
        return false;
#endif
    g_pendingInput = read_character();
    g_inputEof = ( EOF == g_pendingInput );
    return !g_inputEof;
} //keyboard_ready

uint8_t i8008_input( uint8_t port )
{
    if ( port == g_statusPort )
        return keyboard_ready() ? 0x80 : 0;
    if ( port != g_inputPort )
    {
        tracer.Trace( "input port %u unmapped, returning ff\n", port );
        return 0xff;
    }
    int ch;
    if ( g_pendingInput >= 0 )
    {
        ch = g_pendingInput;
        g_pendingInput = -1;
    }
    else
    {
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
            ch = read_character();
    }
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
            "  -m:file     override automatic adjacent .map files for instruction tracing\n"
            "  --in:port   keyboard port, 0..7 (default 2)\n"
            "  --status:port keyboard status, 0..7 (default input port minus one, modulo 8)\n"
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
    const char * inputPath = 0, * symbolPath = 0;
    bool statusSpecified = false;
    for ( int i = 1; i < argc; i++ )
    {
        const char * arg = argv[ i ];
        uint64_t value = 0;
        if ( options && 0 == strcmp( arg, "--" ) ) { options = false; continue; }
        if ( options && ( 0 == strcmp( arg, "--help" ) || 0 == strcmp( arg, "-h" ) ) ) { usage(); return 0; }
        if ( options && 0 == strcmp( arg, "-p" ) ) performance = true;
        else if ( options && 0 == strcmp( arg, "-t" ) ) trace = true;
        else if ( options && 0 == strcmp( arg, "-i" ) ) traceInstructions = true;
        else if ( options && 0 == strncmp( arg, "-m:", 3 ) && arg[ 3 ] ) symbolPath = arg + 3;
        else if ( options && 0 == strncmp( arg, "-l:", 3 ) && arg[ 3 ] ) inputPath = arg + 3;
        else if ( options && '-' == *arg )
        {
            const char * colon = strchr( arg, ':' );
            bool valid = colon && number( colon + 1, value );
            if ( valid && 0 == strncmp( arg, "-a:", 3 ) && value < 16384 ) address = value;
            else if ( valid && 0 == strncmp( arg, "-n:", 3 ) && value ) limit = value;
            else if ( valid && 0 == strncmp( arg, "-s:", 3 ) && value ) hz = value;
            else if ( valid && 0 == strncmp( arg, "--in:", 5 ) && value < 8 ) g_inputPort = (unsigned) value;
            else if ( valid && 0 == strncmp( arg, "--status:", 9 ) && value < 8 )
            {
                g_statusPort = (unsigned) value;
                statusSpecified = true;
            }
            else if ( valid && 0 == strncmp( arg, "--out:", 6 ) && value >= 8 && value < 32 ) g_outputPort = (unsigned) value;
            else { fprintf( stderr, "invalid option: %s\n", arg ); return 1; }
        }
        else
        {
            files.push_back( arg );
        }
    }
    if ( !statusSpecified )
        g_statusPort = ( g_inputPort + 7 ) & 7;
    if ( g_inputPort == g_statusPort )
    {
        fprintf( stderr, "keyboard input and status ports must differ\n" );
        return 1;
    }
    if ( files.empty() ) { usage(); return 1; }
    if ( !tracer.Enable( trace, "ntv8008.log", true ) )
    {
        fprintf( stderr, "can't create ntv8008.log\n" );
        return 1;
    }
    if ( symbolPath && !load_symbols( symbolPath ) ) return 1;
    if ( !symbolPath && trace && traceInstructions )
    {
        for ( size_t i = 0; i < files.size(); i++ )
        {
            std::string path = files[ i ];
            size_t slash = path.find_last_of( "/\\" ), dot = path.find_last_of( '.' );
            if ( dot != std::string::npos && ( slash == std::string::npos || dot > slash ) ) path.erase( dot );
            path += ".map";
            std::ifstream available( path.c_str() );
            if ( available && !load_symbols( path.c_str() ) ) return 1;
        }
    }
    if ( !g_symbols.empty() ) cpu.set_symbol_lookup( symbol_lookup );
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
#ifdef _WIN32
    // Text-mode descriptor reads also perform lookahead for CR/LF translation.
    // The machine's console is a byte interface with its own newline handling.
    _setmode( _fileno( g_input ), _O_BINARY );
#endif
    setvbuf( g_input, 0, _IONBF, 0 );
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
