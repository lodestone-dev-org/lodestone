const express = require("express");
const session = require("express-session");
const bcrypt = require("bcrypt");
const Database = require("better-sqlite3");
const path = require("path");

const app = express();
const db = new Database("users.db");

db.prepare(`
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL
    )
`).run();

app.use(express.urlencoded({ extended: true }));
app.use(express.static(path.join(__dirname, "Frontend")));

app.use(session({
    secret: process.env.SESSION_SECRET || "change-this-secret",
    resave: false,
    saveUninitialized: false,
    cookie: {
        httpOnly: true,
        sameSite: "lax"
    }
}));

app.post("/register", async (req, res) => {
    const { username, password } = req.body;

    if (!username || !password) {
        return res.status(400).send("Username and password are required.");
    }

    const hash = await bcrypt.hash(password, 12);

    try {
        db.prepare(
            "INSERT INTO users (username, password) VALUES (?, ?)"
        ).run(username, hash);

        res.redirect("/");
    } catch {
        res.status(409).send("Username already exists.");
    }
});

app.post("/login", async (req, res) => {
    const { username, password } = req.body;

    const user = db.prepare(
        "SELECT * FROM users WHERE username = ?"
    ).get(username);

    if (!user || !(await bcrypt.compare(password, user.password))) {
        return res.status(401).send("Invalid username or password.");
    }

    req.session.userId = user.id;
    req.session.username = user.username;

    res.redirect("/server_console.html");
});

app.get("/logout", (req, res) => {
    req.session.destroy(() => {
        res.redirect("/");
    });
});

function requireLogin(req, res, next) {
    if (!req.session.userId) {
        return res.redirect("/");
    }

    next();
}

app.get("/server_console.html", requireLogin, (req, res) => {
    res.sendFile(path.join(__dirname, "Frontend", "server_console.html"));
});

app.listen(3000, () => {
    console.log("Server running at http://localhost:3000");
});