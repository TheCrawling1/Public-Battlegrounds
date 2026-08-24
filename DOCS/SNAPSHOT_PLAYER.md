# Combat Snapshot Player

How a single combat is played back on the client, and the contract that keeps
backend and frontend in sync.

## TL;DR

The server resolves the full combat once and emits an ordered list of
commands (`ATTACK`, `COMBAT_DAMAGE`, `DEATH`, …). Alongside each command it
emits a **snapshot** of both bands **after** that command runs. The client is
a pure movie player: for each command it runs the animation, then overwrites
its bands with the server-authored snapshot. It does not reduce deltas, does
not compute hp, does not track keywords. That arithmetic only lives on the
server.

## Data shape

`interpreter_data` (sent to the client after a combat resolves):

```
{
    initial_state:    { player_band: [...], enemy_band: [...] },
    commands:         [cmd_0, cmd_1, ..., cmd_N],
    steps:            [
        { command: cmd_0, state_after: { player_band, enemy_band } },
        { command: cmd_1, state_after: { player_band, enemy_band } },
        ...
    ],
    animation_bundles: [...],
    total_commands:   N + 1,
}
```

Invariants (enforced by `Battlegrounds/tests/test_snapshot_player.py`):

- `len(commands) == len(steps)`
- `steps[i].command is commands[i]`
- Every minion in every snapshot has `_combat_id` and `name`
- `steps[-1].state_after` matches the END command's `final_player_band` /
  `final_enemy_band` on hp, attack, and keywords
- No snapshot has duplicate `_combat_id`s within a side
- All positions are non-negative and unique within a band
- All stats (hp, attack) are non-negative
- Adjacent snapshots do not share list/dict references

## Server side

### `_serialize_band` (`Battlegrounds/game_engine/combat_interpreter.py`)

The **only** egress point for band state. Every field the frontend reads off
a minion must come through here. Current shape:

```
name, health, attack, keywords, position, _combat_id,
golden, stun_count, hide_remaining, permanent_ring_count,
cleave_amount, multi_attack_count, on_any_* triggers, ...
```

`health` is clamped to `max(0, raw)` so transient negative hp during damage
resolution is never visible to the client.

### Snapshot emission

After each command runs through the combat loop, the interpreter calls
`_serialize_band` for both sides and appends `{ command, state_after }` to
`steps`. Snapshots are deep-copied so later mutations in the interpreter
don't retro-edit earlier snapshots (the test suite asserts this).

## Client side

### Core file

`Battlegrounds/js/combat.js` — 2001 lines after the migration (~500 LOC of
legacy reducer code was removed).

### State

```javascript
let frontendCombatState = {
    player_band: [],   // overwritten from snapshots
    enemy_band:  [],   // overwritten from snapshots
    combat_over: false,
    winner:      null,
    round_number: 1,
    combat_log: [],    // built once upfront
    ...
};
```

The bands are write-only via snapshot. Nothing else in `combat.js` mutates
them.

### Playback loop

`stepThroughOneCommand()` → `processInterpreterCommand(cmd)` queues the
command → `processNextAnimation()` runs its animation → `applyCommandEffect`:

1. Dispatches the sound for this command
2. Runs any visual side effect (damage flash, highlight, move, …)
3. Calls `applySnapshotForCommand(command)`, which deep-copies
   `interpreterSteps[cmd.seq].state_after` into `frontendCombatState`
4. Calls `updateFrontendUIData()` and `updateDisplay()`

`combat_over`, `winner`, and `round_number` are set by the command switch
(`END`, `ROUND_START`) since `_serialize_band` only carries minion state.

### Jump and skip

- `skipToEndCommand()` → `snapToStep(interpreterSteps.length - 1)` — copies
  the final snapshot straight into `frontendCombatState`, sets
  `combat_over`/`winner` from the END command. No replay.
- `jumpToCommandIndex(targetIndex)` → `snapToStep(max(0, targetIndex - 1))`.
  The combat log is preserved so every entry stays clickable.

### DEATH batching

When multiple deaths happen in the same phase, `processNextAnimation`
batches them: plays all death visuals in parallel and marks the batched
commands so `stepThroughOneCommand` skips them later. Batched DEATH commands
do NOT run `applyCommandEffect`, so their individual snapshots are not
applied. This is safe because (a) DEATH only toggles a dead flag that isn't
rendered until `REMOVE_FROM_BAND` fires, and (b) the next non-batched
command's snapshot fully overwrites the bands anyway.

## Tests

| Suite | File | What it verifies |
|-------|------|------------------|
| Backend | `Battlegrounds/tests/test_snapshot_player.py` | 22 scenarios, snapshot invariants, END-state matching |
| Frontend | `tests/test_snapshot_player_frontend.js` | 12 scenarios, real `combat.js` in jsdom, per-step band equality plus `jumpToCommandIndex` / `skipToEndCommand` |

Run both:

```
npm run test:snapshot
```

or individually:

```
npm run test:backend      # Battlegrounds/tests/test_snapshot_player.py
npm run test:frontend     # tests/test_snapshot_player_frontend.js
```

The frontend harness requires `npm install` at the repo root (jsdom is a
dev dependency). It loads `Battlegrounds/js/combat.js` verbatim into a
jsdom window, stubs UI/animation hooks as no-ops, generates real
`interpreter_data` via a Python subprocess, and asserts that after each
`stepThroughOneCommand()` the bands deep-equal the server's snapshot for
that command (hp, attack, position, keywords, stun, hide, ring, golden).

## Security note

`interpreter_data.steps[]` is a read-only payload. The client cannot push
snapshots back to influence server state — the server has already run the
combat and banked the result before sending the stream. Tampering with
snapshots in the browser would only desync the client's own display until
the next combat loads.

## How to extend

**Adding a new combat command** (e.g. a new trigger):

1. Emit the command from the relevant handler in
   `Battlegrounds/game_engine/combat_interpreter.py` — the generic snapshot
   plumbing picks it up automatically.
2. Add a case in `combat.js`'s `applyCommandEffect` switch for any
   animation or sound. Do **not** mutate `frontendCombatState` here —
   the snapshot overlay handles that.
3. Add a scenario to `test_snapshot_player.py` that actually exercises the
   new command, so its snapshot stream is pinned.

**Adding a new per-minion field**:

1. Add it to `_serialize_band`. That's the whole client contract.
2. Update `bandToCompareShape` in
   `tests/test_snapshot_player_frontend.js` to include it in per-step
   equality checks.
