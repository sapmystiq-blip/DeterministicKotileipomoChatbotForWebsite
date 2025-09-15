#!/usr/bin/env bash
set -euo pipefail

# Load creds from .env (do not print)
STORE_ID=$(awk -F= '/^ECWID_STORE_ID=/{print $2}' .env)
TOKEN=$(awk -F= '/^ECWID_API_TOKEN=/{print $2}' .env)
BASE="https://app.ecwid.com/api/v3/${STORE_ID}"

# Fetch shipping options and find Pickup method
OPTS_JSON=$(curl -sS "$BASE/profile/shippingOptions" -H "Authorization: Bearer $TOKEN")
PICKUP_ID=$(printf '%s' "$OPTS_JSON" | jq -r '((.items? // .)[] | select(((.fulfilmentType // .fulfillmentType // .type // "")|ascii_downcase)=="pickup") | (.id // .shippingMethodId // .methodId)) | select(.)' | head -n1)
PICKUP_NAME=$(printf '%s' "$OPTS_JSON" | jq -r '((.items? // .)[] | select(((.fulfilmentType // .fulfillmentType // .type // "")|ascii_downcase)=="pickup") | (.title // .name)) | select(.)' | head -n1)
LEAD_MINS=$(printf '%s' "$OPTS_JSON" | jq -r '((.items? // .)[] | select(((.fulfilmentType // .fulfillmentType // .type // "")|ascii_downcase)=="pickup") | (.settings.pickupPreparationTimeMinutes // .fulfillmentTimeInMinutes // .settings.fulfillmentTimeInMinutes // 660)) | select(.)' | head -n1)
HOURS_STR=$(printf '%s' "$OPTS_JSON" | jq -r '((.items? // .)[] | select(((.fulfilmentType // .fulfillmentType // .type // "")|ascii_downcase)=="pickup") | (.pickupBusinessHours // .businessHours // "{}"))' | head -n1)

if [ -z "${PICKUP_ID}" ] || [ -z "${PICKUP_NAME}" ]; then
  echo "Could not find a Pickup shipping method in Ecwid profile" >&2
  exit 1
fi

export LEAD_MINS HOURS_STR

# Build up to 20 candidate slots (date time) within hours and >= lead, stepping hourly
python3 - <<'PY' > .ecwid_candidates.txt
import os, json
from datetime import datetime, timedelta, time
lead=int(os.environ.get('LEAD_MINS','660'))
hours=json.loads(os.environ.get('HOURS_STR') or '{}')
now=datetime.now(); min_t=now+timedelta(minutes=lead)
keys=['MON','TUE','WED','THU','FRI','SAT','SUN']
out=[]
for i in range(0,30):
    d=(now+timedelta(days=i)).date()
    wins=hours.get(keys[d.weekday()],[])
    for start,end in wins:
        sh,sm=map(int,start.split(':'))
        eh,em=map(int,end.split(':'))
        ws=datetime.combine(d,time(sh,sm))
        we=datetime.combine(d,time(eh,em))
        mt=min_t.replace(minute=0, second=0, microsecond=0)
        if min_t>mt:
            mt=mt+timedelta(hours=1)
        cand=max(ws, mt)
        while cand<=we and len(out)<20:
            out.append(f"{d.isoformat()} {cand.strftime('%H:%M')}")
            cand+=timedelta(hours=1)
print("\n".join(out))
PY

echo "Pickup method: ${PICKUP_NAME} (${PICKUP_ID})"
echo "Trying up to 10 slots..."

COUNT=0
while IFS= read -r line; do
  D=${line% *}
  T=${line#* }
  [ -z "$D" ] && continue
  COUNT=$((COUNT+1))
  echo "Attempt $COUNT: $D $T"
  payload=$(jq -n --arg pid "$PICKUP_ID" --arg pname "$PICKUP_NAME" --arg d "$D" --arg t "$T" '{name:"Chat Test",email:"test@example.com",phone:"+358 123 456 789",paymentMethod:"Pay at pickup",paymentStatus:"AWAITING_PAYMENT", shippingOption:{id:$pid, shippingMethodName:$pname, shippingRate:0}, pickupTime:($d+" "+$t), preferredDeliveryDate:$d, preferredDeliveryTime:$t, items:[ {productId:771476057, sku:"00071", quantity:1}, {productId:708500182, sku:"00064", quantity:1} ], customerComment:"Chatbot test order"}')
  RESP=$(curl -sS -w "\nHTTP_STATUS:%{http_code}\n" -X POST "$BASE/orders" -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" --data "$payload") || true
  STATUS=$(printf '%s' "$RESP" | awk -F: '/HTTP_STATUS/ {print $2}' | tr -d '\r\n ')
  BODY=$(printf '%s' "$RESP" | sed -n '1,/^HTTP_STATUS/d')
  if [ "$STATUS" = "200" ]; then
    echo "SUCCESS at $D $T"
    echo "$BODY"
    exit 0
  else
    echo "-> Status $STATUS"
    echo "$BODY"
  fi
  [ $COUNT -ge 10 ] && break
done < .ecwid_candidates.txt

echo "No slot accepted within first 10 candidates. Consider approving a specific time or custom-line fallback." >&2
exit 2
