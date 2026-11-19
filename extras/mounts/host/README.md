# host

A machine's own world, as a template, in Grove alone.

`host.grove` declares three positions. The machine's world makes the composition (one record beneath
`/<self>/io/scope` that names the unit). It seats tenants at `/tenants/[t]`, each with a `limit`. A tenant
asks for a world at `/tenants/[t]/worlds/[w]`: its `name`, the `founding` it starts under, its `mounts`, and
`run` (1 or 0). The machine's world answers at `…/at`: `host`, `http`, `mesa`, or `why` it is not run.

`host_mount.foil` is the pack's own foot. A world that fills a tenant's seat asks, beneath that seat, for the
world prepared for each invited place of every scope it keeps. So a machine's own world, which keeps the host
and fills a seat in it, asks itself; and a world the host started for a tenant's seat asks that host for the
worlds of whatever it keeps in turn. No record says where a world asks: the seat it fills does. `/tenants`
may be opened (`open: <how many>` on its record, beside the `title` and `limit` each seat taken there starts
with), and then anyone at the machine world's door may take a
tenant's seat and is given a world of their own (see the scope mount's `/door/open`).

Nothing in the kernel knows what a host is. Which worlds should be running is what these records say.
`x/host` supervises a machine: it reads the composition at the machine world's agent door, starts and stops
launchers to match, and writes each answer through the same door. It keeps no state of its own.
