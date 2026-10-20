// Matrix page order is chronological after reversal. Keep event IDs unique,
// updating newer representations without sorting equal timestamps arbitrarily.
export function mergeMessages(older,newer){
  const values=new Map();for(const event of [...older,...newer])values.set(event.id,event);
  return [...values.values()];
}
