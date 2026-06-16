import assert from "node:assert/strict";
import test from "node:test";

import { removeMaterialFromList } from "../src/routes/shelfPageViewModel.ts";

test("removeMaterialFromList removes only the deleted material", () => {
  const materials = [{ id: "mat-1" }, { id: "mat-2" }, { id: "mat-3" }];

  assert.deepEqual(removeMaterialFromList(materials, "mat-2"), [
    { id: "mat-1" },
    { id: "mat-3" },
  ]);
});
