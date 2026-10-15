# testlib_pg.sh — a throwaway local PostgreSQL cluster for the closure tests (sourced, not executed).
# Needs the PostgreSQL 16 server binaries (initdb, pg_ctl, postgres) and a non-root user to run them (initdb refuses root).
# Nothing here touches any production host: the cluster lives in /tmp/.pgdata_<port> (a short path: unix socket paths are
# limited to 107 bytes and the server user must be able to traverse it), listens only on a unix socket, and is removed by
# pg_test_stop. Exports PGHOST (socket dir), PGPORT, PGUSER=postgres and PGTEST_DATA (the data directory).
PGBIN="${PGBIN:-/usr/lib/postgresql/16/bin}"
PGTEST_USER="${PGTEST_USER:-pgtest}"

pg_test_start() {   # pg_test_start <port>
  local port="$1" data="/tmp/.pgdata_$1" sock="/tmp/.pgsock_$1"
  [ -x "$PGBIN/initdb" ] || { echo "no PostgreSQL server binaries in $PGBIN" >&2; return 1; }
  if [ "$(id -u)" = 0 ]; then
    id "$PGTEST_USER" >/dev/null 2>&1 || useradd -r -s /usr/sbin/nologin "$PGTEST_USER"
    RUNAS=(runuser -u "$PGTEST_USER" --)
  else
    RUNAS=()
  fi
  rm -rf "$data" "$sock"; mkdir -m 700 "$data"; mkdir -m 700 "$sock"
  [ "$(id -u)" = 0 ] && chown "$PGTEST_USER" "$data" "$sock"
  "${RUNAS[@]}" "$PGBIN/initdb" -D "$data" -U postgres --auth=trust -A trust >/dev/null
  "${RUNAS[@]}" "$PGBIN/pg_ctl" -D "$data" -o "-p $port -k $sock -c listen_addresses='' -c fsync=off" -l "$data/server.log" -w start >/dev/null
  export PGHOST="$sock" PGPORT="$port" PGUSER=postgres PGTEST_DATA="$data"
  pg_isready -h "$sock" -p "$port" -U postgres >/dev/null
}

pg_test_stop() {    # pg_test_stop <port>
  local port="$1" data="/tmp/.pgdata_$1" sock="/tmp/.pgsock_$1"
  if [ -d "$data" ]; then
    if [ "$(id -u)" = 0 ]; then runuser -u "$PGTEST_USER" -- "$PGBIN/pg_ctl" -D "$data" -m fast -w stop >/dev/null 2>&1 || true
    else "$PGBIN/pg_ctl" -D "$data" -m fast -w stop >/dev/null 2>&1 || true; fi
  fi
  rm -rf "$data" "$sock"
}
