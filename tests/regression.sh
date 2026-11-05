#!/bin/bash
# Every case here is a bug the compliance audit found: a rule where following
# the spec produced a red check, or breaking it produced a green one.
# Run after any change to validate_prompt.py or lib/camera.json.
cd "$(dirname "$0")/.."
F=tests/fixtures
pass=0; fail=0
chk(){ n="$1"; want="$2"; shift 2
  "$@" >/dev/null 2>&1; code=$?
  got=$([ $code -eq 0 ] && echo PASS || echo FAIL)
  if [ "$got" = "$want" ]; then echo "  ok   $n ($got)"; pass=$((pass+1))
  else echo "  BAD  $n: wanted $want got $got"; fail=$((fail+1)); fi
}
# pin pacing so a leftover .current_project cannot flip a verdict
V="python3 scripts/validate_prompt.py"
VS="python3 scripts/validate_prompt.py --pacing fast"
chk "filled blocking placeholder passes" PASS $VS --kind seedance $F/blocking.txt
chk "single-direction slash term passes" PASS $VS --kind seedance $F/slash.txt
chk "clock timecode caught"              FAIL $VS --kind seedance $F/badtc.txt
chk "smart-quote dialogue caught"        FAIL $VS --kind seedance $F/smart.txt
chk "NO MUSIC near-miss caught"          FAIL $VS --kind seedance $F/nm.txt
chk "general batch same angle passes"    PASS $V --kind kling --mode general $F/gen1.txt $F/gen2.txt
chk "omni repeat angle caught"           FAIL $V --kind kling --mode omni $F/gen1.txt $F/gen2.txt
chk "omni varied angle passes"           PASS $V --kind kling --mode omni $F/omni1.txt $F/omni2.txt
chk "broken prompt caught"               FAIL $VS --kind seedance $F/bad.txt
chk "correct prompt passes"              PASS $VS --kind seedance $F/good.txt
chk "header out of order caught"         FAIL $VS --kind seedance $F/hdr_bad.txt
chk "40 words told to split, not 'add room'" FAIL $VS --kind seedance --words 40 $F/good.txt
chk "kling box with no duration caught"   FAIL $V --kind kling --mode omni $F/nodur.txt
chk "'chair' does not trip the hair rule" PASS $VS --kind seedance $F/chair.txt
chk "header year line is not a timecode"  PASS $VS --kind seedance $F/yr.txt
chk "mandated Back-to-Back string passes" PASS $VS --kind seedance $F/b2b.txt
chk "0-byte video rejected"               FAIL python3 scripts/watch_take.py --kind action /dev/null
chk "filled over-the-shoulder passes kling"  PASS $V --kind kling --mode omni $F/kling-ots.txt
chk "repeated over-the-shoulder caught"      FAIL $V --kind kling --mode omni $F/kling-ots.txt $F/kling-ots2.txt
rm -rf tests/_tmp && mkdir -p tests/_tmp
chk "assemble.py build produces both ratios" PASS python3 scripts/assemble.py build --config tests/fixtures/assemble-min.json
for r in 9x16 4x5; do
  [ -s "tests/_tmp/out_$r.mp4" ] && { echo "  ok   $r rendered"; pass=$((pass+1)); } \
                                 || { echo "  BAD  $r missing"; fail=$((fail+1)); }
done
rm -rf tests/_tmp
chk "ads money rules (tests/test_ads_rules.py)" PASS python3 tests/test_ads_rules.py
chk "ads stage tracker (tests/test_ads_status.py)" PASS python3 tests/test_ads_status.py
echo; echo "  $pass passed, $fail failed"; exit $fail
