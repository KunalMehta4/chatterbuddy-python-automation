# ChatterBuddy

A command-line personal automation assistant. Type plain commands such as
`weather Toronto`, `add task Finish Python project`, or `set alarm 18:30 Study Python`,
and ChatterBuddy routes each one to the right handler, calls out to a REST API
if the request needs live data, and persists anything worth keeping between
sessions.

The point of the project is the architecture rather than the feature list: a
central command registry instead of a chain of `if`/`elif`, a service layer that
isolates every network call, a repository layer that isolates every file write,
and a test suite that runs the API-dependent code with no network at all.

```
================================
        CHATTERBUDDY
 Your Personal Automation Tool
================================

Type 'help' to view available commands.
Search provider: Wikipedia
  (set TAVILY_API_KEY in .env for general web search)
chatterbuddy> weather Toronto
Weather for Toronto, Ontario, Canada
  Condition   Partly cloudy
  Temperature 24.3°C (feels like 26.1°C)
  Humidity    61%
  Wind        13.7 km/h
  Observed    2026-08-11 14:00 local time
chatterbuddy>
```

---

## Features

| Feature | What it does |
|---|---|
| **Weather** | Current conditions for any place name, resolved through a geocoding API rather than a hard-coded city list |
| **Web search** | Top results from a search API, behind a swappable provider interface |
| **Contacts** | Add, list, search, and remove contacts, with email and phone validation and a uniqueness rule on email |
| **Tasks** | A to-do list with priorities, optional due dates, overdue highlighting, and completion tracking |
| **Alarms** | Daily recurring reminders that fire while the program is running, via a background thread |
| **Persistence** | Everything is stored as JSON with atomic writes and recovery from corrupted files |

### Commands

```
Lookups
  weather <location>                          Show current conditions
  search <query>                              Search the web

Contacts
  add contact <name> <email> <phone>          Save a contact (name may contain spaces)
  show contacts                               List every contact
  find contact <term>                         Search name, email, or phone
  remove contact <id>                         Delete by id

Tasks
  add task <description> [!high|!low] [due:DATE]   Add a task
  show tasks                                  List tasks, unfinished first
  complete task <id>                          Mark done
  remove task <id>                            Delete by id

Alarms
  set alarm <HH:MM> <message>                 Schedule a daily reminder
  show alarms                                 List alarms and their status
  toggle alarm <id>                           Pause or resume without deleting
  remove alarm <id>                           Delete by id

General
  help [command]                              List commands, or explain one
  exit                                         Quit (also: quit, bye)
```

`DATE` accepts `2026-08-20`, `today`, or `tomorrow`. Times accept `18:30`,
`6:30pm`, or `6pm`. Aliases exist for the commands people type by reflex:
`todo`, `tasks`, `contacts`, `alarms`, `done`, `quit`.

---

## Technologies

| | |
|---|---|
| **Language** | Python 3.11+ (`StrEnum`, `X \| None` unions, `dataclass`, `Protocol`, `Generic`) |
| **HTTP** | `requests`, with a shared `Session` and a timeout on every call |
| **APIs** | Open-Meteo (geocoding + forecast), Wikipedia search, Tavily search (optional) |
| **Storage** | JSON files with atomic writes |
| **Config** | `python-dotenv`, environment variables only |
| **Concurrency** | `threading` — one daemon thread and one re-entrant lock |
| **Testing** | `pytest` and `responses` (145 tests) |
| **Linting** | `ruff` |

---

## Architecture

Four layers, with dependencies pointing in exactly one direction:

```
  main.py                     entry point: load .env, build config, run
     |
  app.py                      REPL + composition root
     |
  parser.py / registry.py     normalise input, resolve it to a command
     |
  commands/                   validate arguments, orchestrate, format output
     |            \
  repositories/    services/  collections of records   |   HTTP, filesystem, clock
     |                    \
  data/*.json          REST APIs
```

**Commands may import services and repositories. Services and repositories never
import commands.** Models import neither. That single rule is what makes every
layer independently testable and is the concrete meaning of "separation of
concerns" in this codebase.

### How a command travels through the system

Take `add contact John Smith john@email.com 4165551234`:

1. **`app.py`** reads the line and hands it to `handle()`.
2. **`CommandParser`** collapses whitespace, then tries the longest registered
   command name first: `"add contact"` matches, so the name is
   `add contact` and the arguments are `John Smith john@email.com 4165551234`.
   The command name is lowercased for matching; the arguments keep their
   original casing, which is why `weather Toronto` and names with capitals work.
3. **`CommandRegistry`** looks the name up in a dictionary and returns the
   `AddContactCommand` instance, already holding its repository.
4. **The command** splits the arguments from the right (which is what lets a
   multi-word name work without quotes), validates the email and phone, and asks
   the repository to create the record.
5. **`ContactRepository`** checks the email is not already in use, assigns the
   next id, appends to its list, and calls `save()`.
6. **`JsonStore`** serialises to a temporary file and atomically renames it over
   `data/contacts.json`.
7. **`CommandResult`** travels back up and is printed. If anything raised a
   `ChatterBuddyError` along the way, its message is printed instead — no
   traceback ever reaches the user.

### Project structure

```
chatterbuddy/
├── main.py                      entry point
├── pyproject.toml               dependencies, pytest and ruff config
├── requirements.txt
├── .env.example
│
├── chatterbuddy/
│   ├── app.py                   ChatterBuddy (REPL) + create_app (wiring)
│   ├── config.py                AppConfig.from_env()
│   ├── errors.py                exception hierarchy
│   ├── parser.py                text -> ParsedCommand
│   ├── registry.py              name -> Command
│   │
│   ├── commands/
│   │   ├── base.py              Command ABC, CommandResult
│   │   ├── weather.py  search.py  contacts.py  tasks.py  alarms.py  meta.py
│   │   └── __init__.py          build_registry(): the one place commands are wired
│   │
│   ├── services/
│   │   ├── http_client.py       session, timeouts, HTTP status -> exceptions
│   │   ├── weather_service.py   Open-Meteo geocoding + forecast
│   │   ├── search_service.py    SearchProvider protocol + two implementations
│   │   ├── storage.py           JsonStore: atomic writes, corruption recovery
│   │   └── scheduler.py         due_alarms() + AlarmScheduler thread
│   │
│   ├── repositories/
│   │   ├── base.py              JsonRepository[T]: list + id index + persistence
│   │   └── contacts.py  tasks.py  alarms.py
│   │
│   ├── models/
│   │   └── contact.py  task.py  alarm.py
│   │
│   └── utils/
│       ├── __init__.py          now(): the single clock
│       ├── validators.py        email, phone, time, date
│       └── formatting.py        banner, table rendering
│
├── scripts/
│   ├── verify_geocoding.py      measures real geocoding coverage
│   └── cities.txt               680-name sample used by that script
│
├── data/                        created at runtime, contents gitignored
└── tests/                       10 modules, 145 tests
```

---

## Installation

Requires Python 3.11 or newer.

```bash
git clone https://github.com/KunalMehta4/chatterbuddy-python-automation.git
cd chatterbuddy-python-automation

python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

pip install -r requirements.txt
python main.py
```

That is the whole setup. There is no configuration step, no API key to register
for, and no database to provision — both API-backed commands work immediately.

---

## Configuration

Every setting is optional. To change any of them:

```bash
cp .env.example .env
```

| Variable | Default | Purpose |
|---|---|---|
| `TAVILY_API_KEY` | unset | Enables general web search. Without it, `search` uses Wikipedia. |
| `CHATTERBUDDY_UNITS` | `metric` | `metric` (°C, km/h) or `imperial` (°F, mph) |
| `CHATTERBUDDY_DATA_DIR` | `./data` | Where the JSON files live |
| `CHATTERBUDDY_HTTP_TIMEOUT` | `8` | Seconds before an API call is abandoned |
| `CHATTERBUDDY_SEARCH_RESULTS` | `5` | Results printed per search |
| `CHATTERBUDDY_ALARM_POLL_SECONDS` | `15` | How often the background thread checks for due alarms |

**Weather needs no key.** Open-Meteo is free for non-commercial use without
registration.

**Search works without a key.** The Wikipedia API needs no credentials. Setting
`TAVILY_API_KEY` upgrades `search` to general web search; Tavily's free plan
grants monthly credits without a card on file. `.env` is gitignored, and no
credential appears anywhere in the source.

---

## Usage

```
$ python main.py

chatterbuddy> help
chatterbuddy> weather Toronto
chatterbuddy> weather London, CA               # disambiguate with a country
chatterbuddy> search python property based testing

chatterbuddy> add contact John Smith john@email.com 416-555-1234
Saved John Smith as contact 1 (john@email.com, (416) 555-1234).

chatterbuddy> show contacts
ID  NAME        EMAIL           PHONE
--  ----------  --------------  --------------
1   John Smith  john@email.com  (416) 555-1234

1 contact(s).

chatterbuddy> add task Finish Python project !high due:tomorrow
Added task 1: Finish Python project (priority high, due 2026-08-12)

chatterbuddy> add task Update resume
chatterbuddy> complete task 2
chatterbuddy> show tasks
ID  DONE  PRIORITY  DESCRIPTION            DUE
--  ----  --------  ---------------------  ----------
1   [ ]   high      Finish Python project  2026-08-12
2   [x]   normal    Update resume          -

1 of 2 task(s) outstanding.

chatterbuddy> set alarm 6:30pm Study Python
Alarm 1 set for 18:30 daily: Study Python

chatterbuddy> show alarms
ID  TIME   STATUS  MESSAGE       LAST FIRED
--  -----  ------  ------------  ----------
1   18:30  active  Study Python  never

1 of 1 alarm(s) active.

chatterbuddy> exit
Goodbye!
```

When an alarm comes due while the program is running, it interrupts the prompt:

```
chatterbuddy>
*** ALARM 18:30 *** Study Python
```

Mistakes get help rather than a stack trace:

```
chatterbuddy> show contancts
Unknown command: 'show contancts'. Did you mean: show contacts, add contact?

chatterbuddy> add contact John not-an-email 4165551234
'not-an-email' does not look like an email address (expected something like name@example.com).

chatterbuddy> weather
Usage: weather <location>

chatterbuddy> complete task 99
There is no task with id 99.
```

---

## Testing

```bash
pip install -r requirements.txt
pytest                       # 145 tests
pytest -v                    # per-test names
pytest tests/test_parser.py  # one module
ruff check .                 # lint
```

The suite needs no internet access. It uses two different substitution
strategies, chosen by layer:

| Layer | Substituted with | Why |
|---|---|---|
| Services | `responses`, which intercepts at the `requests` adapter | The tests assert on the actual URL and query string the service builds. A hand-written mock of `WeatherService` would still pass if the parameters were wrong. |
| Commands | Hand-written fake services, real repositories on `tmp_path` | Argument parsing, validation, and formatting, with no mocking framework in the way |
| Scheduler | Nothing — `due_alarms` is a pure function | Two timestamps in, a list out. The midnight-rollover case is exact and instant, with no clock patching and no sleeping. |

What is covered, beyond the happy paths:

- Multi-word command names, longest-prefix resolution, alias resolution,
  argument-case preservation, blank input, typo suggestions
- Missing files, empty files, whitespace-only files, corrupted JSON, valid JSON
  of the wrong shape, unwritable paths, no temp files left behind
- Records that survive a simulated restart, and individually broken records
  being skipped rather than taking the whole file down
- Every API failure mode: 429, 401, 403, 5xx, timeout, connection refused,
  non-JSON body, JSON missing expected fields, unknown weather code
- An unexpected exception inside a command leaving the session usable

### Verifying geocoding coverage

```bash
python scripts/verify_geocoding.py            # all 680 names
python scripts/verify_geocoding.py --limit 25  # quick check
```

This resolves a 680-name sample spanning every inhabited continent against the
live geocoding API and prints the resolution rate. It is the reason the coverage
claim in this README is a measurement rather than an assumption. Transport
failures are counted separately from misses, because a flaky network says
nothing about coverage.

---

## Design decisions

**A command registry, not an `if`/`elif` chain.** Commands are objects in a
dictionary. Adding one means writing a class and adding a line to
`build_registry()`; the parser, the REPL, and `help` all pick it up with no
changes. `help` is generated from the registry, so it cannot drift out of date.

**Longest-prefix parsing for multi-word commands.** `add contact` and
`add task` are distinct commands, not a verb plus a subcommand argument. The
parser joins the first *N* tokens (where *N* is the longest registered name in
words, read from the registry) and walks down to one. At most three dictionary
lookups, and `show` and `show contacts` can coexist unambiguously.

**Commands return `CommandResult`; they never print.** This is what makes the
whole dispatch path testable without capturing stdout, and it means the same
command classes would work behind a web or bot interface unchanged.

**Two layers of error handling, for two audiences.** Everything expected
inherits from `ChatterBuddyError` and carries a message written for a person.
The REPL prints it. Anything else is a bug: the user gets an apology and the
traceback goes to `chatterbuddy.log`.

**HTTP failures are translated at the boundary.** `HttpClient` turns timeouts,
refused connections, 429s, 4xxs, 5xxs, and unparseable bodies into
`NetworkError` or `ApiError`. No `requests` exception type exists above the
service layer, so no command handler needs to know that HTTP is involved.

**JSON, not SQLite.** The data is a few hundred records at most, there are no
queries worth an index, and the files are readable and diffable during
development. JSON adds no dependency and no schema migration story. If this grew
to thousands of records or needed concurrent writers, `JsonRepository` would
become `SqliteRepository`: the three concrete repositories keep their method
signatures and nothing in `commands/` changes.

**Atomic writes, and corrupted files are quarantined rather than overwritten.**
Writes go to a temporary file in the same directory and are renamed with
`os.replace`, which is atomic on POSIX and Windows, so a crash mid-write cannot
truncate the previous good file. A file that no longer parses is renamed to
`contacts.json.corrupt-<timestamp>` and the user is told; they get a working
program *and* keep the file they broke.

**Search sits behind a provider interface, for a real reason.** While this was
being built, Brave moved its Search API off a card-free free tier, Google closed
Custom Search to new customers, and Microsoft retired Bing Search. Wiring a
feature to one vendor means the feature breaks. `SearchProvider` is a `Protocol`
with two implementations; the keyless one is the default so the command works on
a fresh clone, and a key silently upgrades it.

**A daemon thread for alarms, and a lock where it is actually needed.** The
scheduling decision (`due_alarms`) is pure and takes both timestamps as
arguments; the thread is a thin loop around it. `Event.wait` doubles as the sleep
and the shutdown signal, so `exit` stops the thread immediately instead of
waiting out the remainder of a sleep. Because that thread and the main thread
both touch alarms, `JsonRepository` holds an `RLock` — re-entrant because `add`
calls `save`, and both take the lock.

**A single clock function.** Every timestamp comes from `utils.now()`, which
truncates to whole seconds. The stored ISO format keeps only whole seconds, so
generating microsecond precision would mean a record no longer compares equal to
itself after a save-and-load round trip.

**Ids are not reused within a session.** The next id is `max(existing) + 1`,
computed at load and incremented on each add. Deleting the highest-numbered
record and restarting can reuse that id — a known limitation, and a deliberate
trade against changing the file format to carry a counter. SQLite's
`AUTOINCREMENT` would remove it.

**Deliberately simple email validation.** Fully validating an address per RFC
5322 takes a parser, and even a perfect regex cannot tell you whether mail is
deliverable. The pattern catches the mistakes people actually make and gets out
of the way.

---

## Future improvements

- `update contact <id> <field> <value>` — the repository already supports the
  mutation; only a command class is missing
- One-off alarms and weekday schedules, alongside the current daily recurrence
- `news` and `currency` commands, each roughly one service plus one command
  class, which is the claim the architecture is meant to support
- SQLite behind the existing repository interface, once record counts justify it
- Retry with backoff in `HttpClient` for 429 and 5xx responses
- A `--json` output mode, since commands already return structured results
- Packaging as a `pipx`-installable console script (the entry point is already
  declared in `pyproject.toml`)

---

## License

MIT
