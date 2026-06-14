// MG_T08: offline shopping-toggle queue (localStorage, LWW per item).
//
// Phase 1 scope: only the "is_purchased" toggle. Each pending entry stores the
// FINAL desired state for an item, keyed by `${listId}:${itemId}`, so repeated
// offline toggles collapse to the last action (last-write-wins). On reconnect
// the queue is flushed via the existing toggle endpoint (idempotent backend).
import { shoppingApi } from '../api/shopping';

const KEY = 'mg_sync_queue_v1';
export const SYNC_CHANGED_EVENT = 'mg-sync-changed';
export const SYNC_FLUSHED_EVENT = 'mg-sync-flushed';

export interface ToggleEntry {
  listId: number;
  itemId: number;
  isPurchased: boolean;
  ts: number;
}
type QueueMap = Record<string, ToggleEntry>;

function read(): QueueMap {
  try {
    const raw = localStorage.getItem(KEY);
    return raw ? (JSON.parse(raw) as QueueMap) : {};
  } catch {
    return {};
  }
}
function write(q: QueueMap): void {
  try {
    localStorage.setItem(KEY, JSON.stringify(q));
  } catch {
    /* storage full / unavailable — non-fatal */
  }
  window.dispatchEvent(new CustomEvent(SYNC_CHANGED_EVENT));
}

export function enqueueToggle(listId: number, itemId: number, isPurchased: boolean): void {
  const q = read();
  // LWW: newest action for this item replaces any earlier one.
  q[`${listId}:${itemId}`] = { listId, itemId, isPurchased, ts: Date.now() };
  write(q);
}

export function pendingCount(): number {
  return Object.keys(read()).length;
}

let flushing = false;
export async function flushQueue(): Promise<void> {
  if (flushing || !navigator.onLine) return;
  flushing = true;
  try {
    const keys = Object.keys(read());
    for (const k of keys) {
      const cur = read();
      const e = cur[k];
      if (!e) continue;
      try {
        await shoppingApi.toggleItem(e.listId, e.itemId, e.isPurchased);
        const after = read();
        // Drop only if not superseded by a newer toggle queued mid-flight.
        if (after[k] && after[k].ts === e.ts) {
          delete after[k];
          write(after);
        }
      } catch {
        break; // still offline / failed — keep the rest for next reconnect
      }
    }
  } finally {
    flushing = false;
    window.dispatchEvent(new CustomEvent(SYNC_FLUSHED_EVENT));
  }
}
