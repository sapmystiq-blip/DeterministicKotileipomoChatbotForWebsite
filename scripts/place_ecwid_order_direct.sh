#!/usr/bin/env bash
set -euo pipefail

# Load Ecwid credentials from .env
STORE_ID=$(awk -F= '/^ECWID_STORE_ID=/{print $2}' .env)
TOKEN=$(awk -F= '/^ECWID_API_TOKEN=/{print $2}' .env)
BASE="https://app.ecwid.com/api/v3/${STORE_ID}"

# Fetch shipping options
OPTS_JSON=$(curl -sS "$BASE/profile/shippingOptions" -H "Authorization: Bearer $TOKEN")

# Extract pickup option id and name
PICKUP_ID=$(printf '%s' "$OPTS_JSON" | jq -r '((.items? // .)[] | select((.fulfilmentType // .fulfillmentType // .type // "" | ascii_downcase)=="pickup") | (.id // .shippingMethodId // .methodId)) | select(.)' | head -n1)
if [ -z "${PICKUP_ID}" ]; then
  PICKUP_ID=$(printf '%s' "$OPTS_JSON" | jq -r '((.items? // .)[0] | (.id // .shippingMethodId // .methodId))')
fi
PICKUP_NAME=$(printf '%s' "$OPTS_JSON" | jq -r '((.items? // .)[] | select((.fulfilmentType // .fulfillmentType // .type // "" | ascii_downcase)=="pickup") | (.title // .name)) | select(.)' | head -n1)
if [ -z "${PICKUP_NAME}" ]; then
  PICKUP_NAME=$(printf '%s' "$OPTS_JSON" | jq -r '((.items? // .)[0] | (.title // .name // "Pickup"))')
fi

# Lead minutes and business hours JSON
LEAD_MINS=$(printf '%s' "$OPTS_JSON" | jq -r '((.items? // .)[] | select((.fulfilmentType // .fulfillmentType // .type // "" | ascii_downcase)=="pickup") | (.settings.pickupPreparationTimeMinutes // .fulfillmentTimeInMinutes // .settings.fulfillmentTimeInMinutes // 0)) | select(.)' | head -n1)
HOURS_STR=$(printf '%s' "$OPTS_JSON" | jq -r '((.items? // .)[] | select((.fulfilmentType // .fulfillmentType // .type // "" | ascii_downcase)=="pickup") | (.pickupBusinessHours // .businessHours // "{}"))' | head -n1)
export LEAD_MINS HOURS_STR

# Compute next valid slot inside hours and after lead time
read -r PICKUP_DATE PICKUP_TIME <<EOF
$(python3 - <<'PY'
import sys, json, os
from datetime import datetime, timedelta, time
lead=int(os.environ.get('LEAD_MINS','0'))
hours=json.loads(os.environ.get('HOURS_STR') or '{}')
now=datetime.now()
min_time=now+timedelta(minutes=lead)
keys=['MON','TUE','WED','THU','FRI','SAT','SUN']
for i in range(0,30):
    day=now.date()+timedelta(days=i)
    wins=hours.get(keys[day.weekday()],[])
    for start,end in wins:
        sh,sm=map(int,start.split(':'))
        cand=datetime.combine(day, time(sh,sm))
        if cand>=min_time:
            print(day.isoformat(), start)
            sys.exit(0)
print('', '')
PY)
EOF

if [ -z "${PICKUP_DATE}" ] || [ -z "${PICKUP_TIME}" ]; then
  echo "No valid pickup slot found in next 30 days" >&2
  exit 1
fi

# Parse flags: --product-id <id>, --sku <sku>, --custom-name <name>, --custom-price <price>, --quantity <n>
PRODUCT_ID=""
SKU=""
CUSTOM_NAME=""
CUSTOM_PRICE=""
QUANTITY="1"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --product-id)
      PRODUCT_ID="$2"; shift 2 ;;
    --sku)
      SKU="$2"; shift 2 ;;
    --custom-name)
      CUSTOM_NAME="$2"; shift 2 ;;
    --custom-price)
      CUSTOM_PRICE="$2"; shift 2 ;;
    --quantity)
      QUANTITY="$2"; shift 2 ;;
    *) echo "Unknown argument: $1" >&2; exit 2 ;;
  esac
done

# Resolve product if not provided
if [ -z "$PRODUCT_ID" ] && [ -z "$SKU" ] && [ -z "$CUSTOM_NAME" ]; then
  PRODUCT_ID=$(curl -sS "$BASE/products?enabled=true&inStock=true&limit=5" -H "Authorization: Bearer $TOKEN" | jq -r '.items[0].id')
  if [ -z "${PRODUCT_ID}" ] || [ "${PRODUCT_ID}" = "null" ]; then
    echo "No product found" >&2
    exit 1
  fi
fi

# Create the order
if [ -n "$CUSTOM_NAME" ]; then
  PRICE_DOT=${CUSTOM_PRICE/,/.}
  if [ -n "$SKU" ]; then
    ITEM_PAYLOAD="{ \"name\": \"${CUSTOM_NAME}\", \"price\": ${PRICE_DOT}, \"quantity\": ${QUANTITY}, \"sku\": \"${SKU}\" }"
  else
    ITEM_PAYLOAD="{ \"name\": \"${CUSTOM_NAME}\", \"price\": ${PRICE_DOT}, \"quantity\": ${QUANTITY} }"
  fi
elif [ -n "$SKU" ]; then
  ITEM_PAYLOAD="{ \"sku\": \"${SKU}\", \"quantity\": ${QUANTITY} }"
else
  ITEM_PAYLOAD="{ \"productId\": ${PRODUCT_ID}, \"quantity\": ${QUANTITY} }"
fi

RESP_ALL=$(curl -sS -i -w "\nHTTP_STATUS:%{http_code}\n" -X POST "$BASE/orders" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  --data-binary @- <<JSON
{
  "name": "API Test",
  "paymentMethod": "Pay at pickup",
  "paymentStatus": "AWAITING_PAYMENT",
  "shippingOption": {
    "id": "${PICKUP_ID}",
    "shippingMethodName": "${PICKUP_NAME}",
    "shippingRate": 0
  },
  "preferredDeliveryDate": "${PICKUP_DATE}",
  "preferredDeliveryTime": "${PICKUP_TIME}",
  "items": [ ${ITEM_PAYLOAD} ]
}
JSON
)

# Debug output
if [ "${DEBUG:-0}" != "0" ]; then
  echo "--- Request ---"
  echo "POST $BASE/orders"
  echo "Authorization: Bearer ***REDACTED***"
  echo "Content-Type: application/json"
  echo "ShippingOption.id: $PICKUP_ID"
  echo "Pickup: ${PICKUP_DATE} ${PICKUP_TIME}"
  if [ -n "$SKU" ]; then
    echo "Item: SKU=$SKU"
  elif [ -n "$CUSTOM_NAME" ]; then
    echo "Item: CUSTOM name='$CUSTOM_NAME' price='$CUSTOM_PRICE' qty=$QUANTITY"
  else
    echo "Item: productId=$PRODUCT_ID"
  fi
fi

echo "--- Response ---"
echo "$RESP_ALL"
