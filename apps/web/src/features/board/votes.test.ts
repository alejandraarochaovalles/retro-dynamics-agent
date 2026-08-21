import { describe, expect, it } from "vitest";
import { countVotes, hasVoted, toggleVote } from "./votes";

describe("countVotes", () => {
  it("counts how many participants voted for a note", () => {
    const votes = { ale: ["n1", "n2"], jo: ["n1"], sam: [] };
    expect(countVotes(votes, "n1")).toBe(2);
    expect(countVotes(votes, "n2")).toBe(1);
    expect(countVotes(votes, "n3")).toBe(0);
  });

  it("returns 0 for an empty votes map", () => {
    expect(countVotes({}, "n1")).toBe(0);
  });
});

describe("hasVoted", () => {
  it("reports whether a specific participant voted for a note", () => {
    const votes = { ale: ["n1"] };
    expect(hasVoted(votes, "ale", "n1")).toBe(true);
    expect(hasVoted(votes, "ale", "n2")).toBe(false);
  });

  it("returns false for a participant with no entry yet", () => {
    expect(hasVoted({}, "ale", "n1")).toBe(false);
  });
});

describe("toggleVote", () => {
  it("adds the note id when not present", () => {
    expect(toggleVote([], "n1")).toEqual(["n1"]);
    expect(toggleVote(["n1"], "n2")).toEqual(["n1", "n2"]);
  });

  it("removes the note id when already present (vote/unvote per ADR-0004)", () => {
    expect(toggleVote(["n1"], "n1")).toEqual([]);
    expect(toggleVote(["n1", "n2"], "n1")).toEqual(["n2"]);
  });

  it("does not mutate the input array", () => {
    const original = ["n1"];
    toggleVote(original, "n2");
    expect(original).toEqual(["n1"]);
  });
});
