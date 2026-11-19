# fleet

Machines as seats, in Grove alone.

`fleet.grove` declares three positions. The world that fronts a domain makes the composition and seats a
machine at `/machines/[m]`. The machine's own world fills the seat and says, beneath it, each world it runs
(`worlds/[w]`: `name`, `host`, `http`) and how much room it has (`room`: `seats`, `door`). Only the keeper
reads these.

`fleet_mount.foil` is the pack's own foot. A world that fills a machine's seat writes those records from
what it already holds: the answers its own host wrote, and what its host's tenants say is open. Nothing in
the kernel knows what a fleet or a machine is.

Outside the worlds, two scripts read the composition at the keeper's agent door. `x/host --fleet` keeps the
front's routes: every name any machine says it runs goes to that machine, and `--start` names what is sent
to the door of the machine with the most room. `x/provision` creates a server for a machine's seat that
holds an invitation and no world, and starts `x/machine` there under the seat's link.
