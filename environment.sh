source ~lsinger/opt/healpix/environment.sh
source ~lsinger/opt/novas/environment.sh
export PATH=~gdb_processor/leo/bin$(test -n "$PATH" && echo :$PATH)
export PYTHONPATH=~gdb_processor/leo/lib/$(python -c  "import sys;print 'python%d.%d' % sys.version_info[:2]")/site-packages$(test -n "$PYTHONPATH" && echo :$PYTHONPATH)

