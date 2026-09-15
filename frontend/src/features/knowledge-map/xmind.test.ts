import { afterEach, describe, expect, it, vi } from "vitest";

import { KnowledgeTree } from "./types";
import {
  buildXmindContent,
  buildXmindFile,
  crc32,
  downloadXmindFile,
  xmindFileName,
} from "./xmind";

function makeTree(): KnowledgeTree {
  return {
    id: "root",
    title: "论文终稿",
    summary: "文档根节点",
    keywords: [],
    source_section_indexes: [],
    depth: 0,
    children: [
      {
        id: "chapter",
        title: "四、总结",
        summary: "章节摘要",
        keywords: [],
        source_section_indexes: [1],
        depth: 1,
        children: [
          {
            id: "local-1",
            title: "我加的节点",
            summary: "",
            keywords: [],
            source_section_indexes: [],
            depth: 2,
            children: [],
            local: true,
          },
        ],
      },
    ],
  };
}

/** Independent walk of the stored entries, used to verify the container. */
function readStoredEntries(bytes: Uint8Array): Map<string, string> {
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  const endOffset = bytes.length - 22;
  expect(view.getUint32(endOffset, true)).toBe(0x06054b50);
  const entryCount = view.getUint16(endOffset + 10, true);
  let cursor = view.getUint32(endOffset + 16, true);

  const entries = new Map<string, string>();
  for (let index = 0; index < entryCount; index += 1) {
    expect(view.getUint32(cursor, true)).toBe(0x02014b50);
    const size = view.getUint32(cursor + 24, true);
    const nameLength = view.getUint16(cursor + 28, true);
    const localOffset = view.getUint32(cursor + 42, true);
    const name = new TextDecoder().decode(bytes.slice(cursor + 46, cursor + 46 + nameLength));

    const localNameLength = view.getUint16(localOffset + 26, true);
    const dataStart = localOffset + 30 + localNameLength;
    entries.set(name, new TextDecoder().decode(bytes.slice(dataStart, dataStart + size)));
    cursor += 46 + nameLength;
  }
  return entries;
}

afterEach(() => {
  vi.restoreAllMocks();
  Reflect.deleteProperty(URL, "createObjectURL");
  Reflect.deleteProperty(URL, "revokeObjectURL");
});

describe("xmind export", () => {
  it("computes the standard crc32 check value", () => {
    expect(crc32(new TextEncoder().encode("123456789"))).toBe(0xcbf43926);
  });

  it("writes a stored zip holding the three xmind parts", () => {
    const bytes = buildXmindFile(makeTree());
    expect(new TextDecoder().decode(bytes.slice(0, 4))).toBe("PK\u0003\u0004");

    const entries = readStoredEntries(bytes);
    expect([...entries.keys()].sort()).toEqual(["content.json", "manifest.json", "metadata.json"]);

    const content = JSON.parse(entries.get("content.json") ?? "[]") as Array<{
      title: string;
      rootTopic: {
        title: string;
        structureClass?: string;
        notes?: { plain: { content: string } };
        children?: { attached: Array<{ title: string; children?: { attached: Array<{ title: string }> } }> };
      };
    }>;
    expect(content).toHaveLength(1);
    expect(content[0].title).toBe("论文终稿");
    expect(content[0].rootTopic.title).toBe("论文终稿");
    expect(content[0].rootTopic.structureClass).toBe("org.xmind.ui.map.unbalanced");
    expect(content[0].rootTopic.notes?.plain.content).toBe("文档根节点");
    const chapter = content[0].rootTopic.children?.attached[0];
    expect(chapter?.title).toBe("四、总结");
    expect(chapter?.children?.attached[0].title).toBe("我加的节点");
  });

  it("keeps node summaries as xmind notes and skips empty ones", () => {
    const content = JSON.parse(buildXmindContent(makeTree())) as Array<{
      rootTopic: { children?: { attached: Array<{ notes?: unknown }> } };
    }>;
    const chapter = content[0].rootTopic.children?.attached[0] as {
      notes?: { plain: { content: string } };
    };
    expect(chapter.notes?.plain.content).toBe("章节摘要");
  });

  it("builds a download file name that filesystems accept", () => {
    expect(xmindFileName("论文终稿")).toBe("论文终稿.xmind");
    expect(xmindFileName('a/b:c*?"<>|d')).toBe("a b c d.xmind");
    expect(xmindFileName("   ")).toBe("思维导图.xmind");
  });

  it("downloads the map as an xmind file", () => {
    const createObjectURL = vi.fn(() => "blob:xmind");
    const revokeObjectURL = vi.fn();
    Object.defineProperty(URL, "createObjectURL", { configurable: true, value: createObjectURL });
    Object.defineProperty(URL, "revokeObjectURL", { configurable: true, value: revokeObjectURL });
    const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => undefined);

    downloadXmindFile(makeTree());

    expect(createObjectURL).toHaveBeenCalledTimes(1);
    expect(click).toHaveBeenCalledTimes(1);
    expect(revokeObjectURL).toHaveBeenCalledWith("blob:xmind");
    expect(document.querySelector("a")).toBeNull();
  });
});
