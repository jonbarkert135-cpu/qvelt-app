import { describe, expect, it } from "vitest";
import fixtures from "../fixtures/stream-events.json";
import { parseEvent } from "./events";

describe("shared wire fixtures", () => {
  for (const { name, event } of fixtures.valid) {
    it(`accepts ${name}`, () => expect(parseEvent(JSON.stringify(event))).toEqual(event));
  }
  for (const { name, json } of fixtures.invalid) {
    it(`rejects ${name} without leaking payload`, () => {
      expect(() => parseEvent(json)).toThrowError(new TypeError("Invalid stream event"));
    });
  }
});
