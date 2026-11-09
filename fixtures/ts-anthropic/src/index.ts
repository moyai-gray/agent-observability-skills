import Anthropic from "@anthropic-ai/sdk";
import express from "express";

const anthropic = new Anthropic();
const app = express();
app.use(express.json());

app.post("/ask", async (req, res) => {
  const message = await anthropic.messages.create({
    model: "claude-haiku-5-5",
    max_tokens: 512,
    messages: [{ role: "user", content: req.body.question }],
  });
  const block = message.content[0];
  res.json({ answer: block.type === "text" ? block.text : "" });
});

app.listen(3000);
