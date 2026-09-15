import { KnowledgeTree, KnowledgeTreeNode } from "./types";

export const XMIND_MEDIA_TYPE = "application/vnd.xmind.workbook";

const encoder = new TextEncoder();
let topicCounter = 0;

/** XMind 2020 and later read `content.json`; this is the sheet/topic shape it expects. */
export function buildXmindContent(tree: KnowledgeTree): string {
  return JSON.stringify([
    {
      id: nextId("sheet"),
      class: "sheet",
      title: tree.title || "思维导图",
      rootTopic: toTopic(tree, true),
    },
  ]);
}

export function buildXmindMetadata(): string {
  return JSON.stringify({
    creator: { name: "AI Knowledge Structuring Agent", version: "1.0" },
  });
}

export function buildXmindManifest(): string {
  return JSON.stringify({ "file-entries": { "content.json": {}, "metadata.json": {} } });
}

export function buildXmindFile(tree: KnowledgeTree): Uint8Array {
  return createZip([
    { name: "content.json", data: encoder.encode(buildXmindContent(tree)) },
    { name: "metadata.json", data: encoder.encode(buildXmindMetadata()) },
    { name: "manifest.json", data: encoder.encode(buildXmindManifest()) },
  ]);
}

/** A file name that survives Windows, macOS and Linux downloads. */
export function xmindFileName(title: string): string {
  const cleaned = title.replace(/[\\/:*?"<>|\u0000-\u001f]/g, " ").replace(/\s+/g, " ").trim();
  return `${cleaned || "思维导图"}.xmind`;
}

/** Trigger the browser download for the (possibly edited) map. */
export function downloadXmindFile(tree: KnowledgeTree): void {
  const blob = new Blob([buildXmindFile(tree)], { type: XMIND_MEDIA_TYPE });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = xmindFileName(tree.title);
  anchor.rel = "noopener";
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

function toTopic(node: KnowledgeTreeNode, isRoot = false): Record<string, unknown> {
  const topic: Record<string, unknown> = {
    id: nextId("topic"),
    class: "topic",
    title: node.title || "新节点",
  };
  // XMind's own default for a new map: the balanced mind map, branches on both sides.
  if (isRoot) topic.structureClass = "org.xmind.ui.map.unbalanced";
  if (node.summary.trim()) topic.notes = { plain: { content: node.summary } };
  if (node.children.length > 0) {
    topic.children = { attached: node.children.map((child) => toTopic(child)) };
  }
  return topic;
}

function nextId(prefix: string): string {
  topicCounter += 1;
  return `${prefix}-${topicCounter}-${Math.random().toString(36).slice(2, 8)}`;
}

type ZipEntry = { name: string; data: Uint8Array };

/**
 * Minimal ZIP writer (stored, no compression). XMind reads stored entries, and
 * writing the container here keeps the export free of extra dependencies.
 */
function createZip(entries: ZipEntry[]): Uint8Array {
  const localParts: Uint8Array[] = [];
  const centralParts: Uint8Array[] = [];
  let offset = 0;

  for (const entry of entries) {
    const nameBytes = encoder.encode(entry.name);
    const crc = crc32(entry.data);

    const local = new Uint8Array(30 + nameBytes.length);
    const localView = new DataView(local.buffer);
    localView.setUint32(0, 0x04034b50, true);
    localView.setUint16(4, 20, true);
    localView.setUint16(6, 0, true);
    localView.setUint16(8, 0, true); // stored
    localView.setUint16(10, 0, true);
    localView.setUint16(12, 0x21, true); // 1980-01-01
    localView.setUint32(14, crc, true);
    localView.setUint32(18, entry.data.length, true);
    localView.setUint32(22, entry.data.length, true);
    localView.setUint16(26, nameBytes.length, true);
    localView.setUint16(28, 0, true);
    local.set(nameBytes, 30);

    const central = new Uint8Array(46 + nameBytes.length);
    const centralView = new DataView(central.buffer);
    centralView.setUint32(0, 0x02014b50, true);
    centralView.setUint16(4, 20, true);
    centralView.setUint16(6, 20, true);
    centralView.setUint16(8, 0, true);
    centralView.setUint16(10, 0, true);
    centralView.setUint16(12, 0, true);
    centralView.setUint16(14, 0x21, true);
    centralView.setUint32(16, crc, true);
    centralView.setUint32(20, entry.data.length, true);
    centralView.setUint32(24, entry.data.length, true);
    centralView.setUint16(28, nameBytes.length, true);
    centralView.setUint16(30, 0, true);
    centralView.setUint16(32, 0, true);
    centralView.setUint16(34, 0, true);
    centralView.setUint16(36, 0, true);
    centralView.setUint32(38, 0, true);
    centralView.setUint32(42, offset, true);
    central.set(nameBytes, 46);

    localParts.push(local, entry.data);
    centralParts.push(central);
    offset += local.length + entry.data.length;
  }

  const centralSize = centralParts.reduce((total, part) => total + part.length, 0);
  const end = new Uint8Array(22);
  const endView = new DataView(end.buffer);
  endView.setUint32(0, 0x06054b50, true);
  endView.setUint16(4, 0, true);
  endView.setUint16(6, 0, true);
  endView.setUint16(8, entries.length, true);
  endView.setUint16(10, entries.length, true);
  endView.setUint32(12, centralSize, true);
  endView.setUint32(16, offset, true);
  endView.setUint16(20, 0, true);

  return concatBytes([...localParts, ...centralParts, end]);
}

let crcTable: Uint32Array | null = null;

export function crc32(data: Uint8Array): number {
  crcTable ??= buildCrcTable();
  let crc = 0xffffffff;
  for (const byte of data) {
    crc = crcTable[(crc ^ byte) & 0xff] ^ (crc >>> 8);
  }
  return (crc ^ 0xffffffff) >>> 0;
}

function buildCrcTable(): Uint32Array {
  const table = new Uint32Array(256);
  for (let index = 0; index < 256; index += 1) {
    let value = index;
    for (let bit = 0; bit < 8; bit += 1) {
      value = value & 1 ? 0xedb88320 ^ (value >>> 1) : value >>> 1;
    }
    table[index] = value >>> 0;
  }
  return table;
}

function concatBytes(parts: Uint8Array[]): Uint8Array {
  const total = parts.reduce((size, part) => size + part.length, 0);
  const result = new Uint8Array(total);
  let offset = 0;
  for (const part of parts) {
    result.set(part, offset);
    offset += part.length;
  }
  return result;
}
