#pragma once

#include <stdio.h>
#include <stdarg.h>

// Small portable file tracer, following ntvao's Enable/Trace/Shutdown convention.
class CTrace
{
    FILE * fp;
    CTrace( const CTrace & ) = delete;
    CTrace & operator=( const CTrace & ) = delete;

public:
    CTrace() : fp( 0 ) {}
    ~CTrace() { Shutdown(); }

    bool Enable( bool enable, const char * path, bool destroyContents = true )
    {
        Shutdown();
        if ( enable )
            fp = fopen( path, destroyContents ? "w" : "a" );
        return !enable || 0 != fp;
    } //Enable

    bool IsEnabled() const { return 0 != fp; }

    void Shutdown()
    {
        if ( fp )
        {
            fclose( fp );
            fp = 0;
        }
    } //Shutdown

    void Trace( const char * format, ... )
    {
        if ( fp )
        {
            va_list args;
            va_start( args, format );
            vfprintf( fp, format, args );
            va_end( args );
            fflush( fp );
        }
    } //Trace
}; //CTrace
