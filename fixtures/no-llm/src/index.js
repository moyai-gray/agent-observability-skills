import express from "express";

const todos = [];
const app = express();
app.use(express.json());
app.get("/todos", (_req, res) => res.json(todos));
app.post("/todos", (req, res) => {
  todos.push({ id: todos.length + 1, title: req.body.title });
  res.status(201).json(todos.at(-1));
});
app.listen(3000);
