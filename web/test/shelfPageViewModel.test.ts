import assert from "node:assert/strict";
import test from "node:test";

import { isPdfFile, pickPdfFile, removeMaterialFromList } from "../src/routes/shelfPageViewModel.ts";

test("removeMaterialFromList removes only the deleted material", () => {
  const materials = [{ id: "mat-1" }, { id: "mat-2" }, { id: "mat-3" }];

  assert.deepEqual(removeMaterialFromList(materials, "mat-2"), [
    { id: "mat-1" },
    { id: "mat-3" },
  ]);
});

test("isPdfFile accepts PDF MIME type or file extension", () => {
  assert.equal(isPdfFile({ name: "source.bin", type: "application/pdf" }), true);
  assert.equal(isPdfFile({ name: "reading.PDF", type: "" }), true);
  assert.equal(isPdfFile({ name: "notes.txt", type: "text/plain" }), false);
});

test("pickPdfFile selects the first PDF candidate from pasted or dropped files", () => {
  const files = [
    { name: "cover.png", type: "image/png" },
    { name: "course.pdf", type: "" },
    { name: "appendix.pdf", type: "application/pdf" },
  ];

  assert.deepEqual(pickPdfFile(files), {
    file: files[1],
    hasFiles: true,
  });
  assert.deepEqual(pickPdfFile([{ name: "notes.txt", type: "text/plain" }]), {
    file: null,
    hasFiles: true,
  });
  assert.deepEqual(pickPdfFile(null), {
    file: null,
    hasFiles: false,
  });
});
