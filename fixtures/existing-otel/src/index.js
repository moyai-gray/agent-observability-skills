import express from "express";
import OpenAI from "openai";

const openai = new OpenAI();
const app = express();
app.use(express.json());

app.post("/orders/:id/explain", async (req, res) => {
  const completion = await openai.chat.completions.create({
    model: "gpt-4.1-mini",
    messages: [{ role: "user", content: `Explain order status: ${JSON.stringify(req.body)}` }],
  });
  res.json({ explanation: completion.choices[0].message.content });
});

app.listen(3000);
