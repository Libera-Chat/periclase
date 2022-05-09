# pericase - CTCP scanner and banner

The main instance of periclase running on Libera Chat uses the nickname `libera-connect` to be more evidently an official piece of the network.

Periclase holds two sets of patterns; one set (`trigger`s) tells periclase which clients should receive a `CTCP VERSION` request upon connect, the other set (`reject`s) tells periclase which `CTCP VERSION` responses should incite a `KLINE`.

Periclase will accept messages in private message (`/query libera-connect trigger list`) and in-channel (`libera-connect: trigger list`.)

Periclase `trigger`s have 4 possible actions; in order of precedence:
  * `DISABLED` (do nothing, skip these triggers but show them in `trigger list`)
  * `IGNORE` (don't run `CTCP VERSION` and don't send an explanatory `NOTICE`)
  * `QUIETSCAN` (run `CTCP VERSION` but don't send an explanatory `NOTICE`)
  * `SCAN` (run `CTCP VERSION` and send an explanatory `NOTICE`)

## trigger commands

### trigger list
```
<jess> trigger list
-libera-connect- IGNORE:
-libera-connect-   1: /^[^@]+@2001:470:69fc:105:\S+ @\S+:/
-libera-connect- SCAN:
-libera-connect-   2: /^jess-test!/
-libera-connect- (2 total)
```

### trigger add
the argument given to this is a `/regex/` that is run against `nickname!username@hostname realname`

```
<jess> trigger add /^jess-test-2!/ scan
-libera-connect- added trigger 2
<jess> trigger add /^jess-test-2!/ floob
-libera-connect- unknown action 'FLOOB', expected IGNORE, QUIETSCAN, SCAN
```

### trigger set

```
<jess> trigger set 2 scan
-libera-connect- trigger 2 is already SCAN
<jess> trigger set 2 disabled
-libera-connect- set trigger 2 to DISABLED
```

### trigger get
```
<jess> trigger get 2
-libera-connect- /^jess-test-2!/
-libera-connect- action: SCAN
-libera-connect-  since: 2022-05-06T17:07:27.485085
-libera-connect-  adder: jess (jess!meow@libera/staff/cat/jess)
```

### trigger remove
```
<jess> trigger remove 2
-libera-connect- removed trigger 2 (/^jess-test-2/)
```

## Reject commands

### reject list

```
<jess> reject list
-libera-connect- 1: /^matrix-appservice-irc 0.33.1 bridged via /
-libera-connect- (1 total)
```

### reject add

```
<jess> reject add /^matrix-appservice-irc 0.33.2 bridged via / You are running an outdated and vulnerable version of matrix-appservice-irc.|oper reason here
-libera-connect- added reject 2
```

### reject get

```
<jess> reject get 2
-libera-connect- /^matrix-appservice-irc 0.33.2 bridged via /
-libera-connect- reason: You are running an outdated and vulnerable version of matrix-appservice-irc.|oper reason here
-libera-connect-  since: 2022-05-06T17:07:52.070256
-libera-connect-  adder: jess (jess!meow@libera/staff/cat/jess)
```

### reject remove

```
<jess> reject remove 2
-libera-connect- removed reject 2 (/^matrix-appservice-irc 0.33.2 bridged via /)
```
