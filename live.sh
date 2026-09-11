#!/bin/sh
# Keep-alive exword session: one connection, commands fed through a FIFO.
#   ./live.sh [library|text] > session-NN-live.log 2>&1 &   # waits for the dictionary, then connects
#   echo 'list' > .live.in                                   # send a command
#   echo disconnect > .live.in; pkill -f '[l]ive.sh'         # stop (disconnect drops USB)
cd "$(dirname "$0")" || exit 1
F=.live.in
rm -f "$F" && mkfifo "$F" || exit 1
until ioreg -p IOUSB -l -w0 | grep -q '"USB Product Name" = "CESG502"'; do sleep 3; done
sleep 3
./libexword/src/exword < "$F" &
EX=$!
# ponytail: 30 s `model` ping keeps the link busy; unproven whether it stops auto power-off
{ echo "connect ${1:-text}"; while kill -0 $EX 2>/dev/null; do sleep 30; echo model; done; } > "$F"
