import { anthropic } from "@ai-sdk/anthropic";
import { generateText } from "ai";

export async function draftReply(ticket: string) {
  const { text } = await generateText({
    model: anthropic("claude-sonnet-5-5"),
    prompt: `Draft a support reply to:\n\n${ticket}`,
  });
  return text;
}
