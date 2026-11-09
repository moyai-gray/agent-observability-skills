import { openai } from "@ai-sdk/openai";
import { generateText } from "ai";

export async function summarize(text: string) {
  const { text: summary } = await generateText({
    model: openai("gpt-4.1-mini"),
    prompt: `Summarize in one sentence:\n\n${text}`,
  });
  return summary;
}
