const API_BASE = "http://localhost:8000/api";

async function updateStatus() {
    try {
        const res = await fetch(`${API_BASE}/status`);
        const data = await res.json();
        
        // Render total strength
        document.getElementById("strength-val").innerText = data.total_strength;
        
        // Console logger logic
        const consoleBox = document.getElementById("log-console");
        if (consoleBox.dataset.lastLog !== data.last_log) {
            consoleBox.dataset.lastLog = data.last_log;
            const entry = document.createElement("div");
            entry.className = "py-0.5 border-b border-slate-900/40";
            entry.innerHTML = `<span class="text-slate-500 font-semibold">[${new Date().toLocaleTimeString()}]</span> ${data.last_log}`;
            consoleBox.prepend(entry);
        }

        // Present Table population
        const pBody = document.getElementById("present-body");
        pBody.innerHTML = "";
        if (data.present.length === 0) {
            pBody.innerHTML = `<tr><td colspan="3" class="px-4 py-4 text-center text-slate-500 text-xs">No students currently in classroom</td></tr>`;
        } else {
            data.present.forEach(s => {
                pBody.innerHTML += `<tr class="border-b border-slate-800 hover:bg-slate-800/20 transition">
                    <td class="px-4 py-2.5 font-medium text-sm text-slate-200">${s.name}</td>
                    <td class="px-4 py-2.5 text-xs text-slate-400">${s.roll_number}</td>
                    <td class="px-4 py-2.5 text-xs text-teal-400">${s.entry_time}</td>
                </tr>`;
            });
        }

        // Absent Table population
        const aBody = document.getElementById("absent-body");
        aBody.innerHTML = "";
        if (data.absent.length === 0) {
            aBody.innerHTML = `<tr><td colspan="2" class="px-4 py-4 text-center text-slate-500 text-xs">All registered students are inside</td></tr>`;
        } else {
            data.absent.forEach(s => {
                aBody.innerHTML += `<tr class="border-b border-slate-800 hover:bg-slate-800/20 transition">
                    <td class="px-4 py-2.5 font-medium text-sm text-slate-300">${s.name}</td>
                    <td class="px-4 py-2.5 text-xs text-slate-400">${s.roll_number}</td>
                </tr>`;
            });
        }
    } catch (err) {
        console.error("Dashboard connection failed with Backend API.", err);
    }
}

async function triggerAction(action) {
    try {
        await fetch(`${API_BASE}/trigger?action=${action}`, { method: "POST" });
    } catch (err) {
        console.error("Simulated manual trigger command failed:", err);
    }
}

async function reloadDatabase() {
    try {
        const res = await fetch(`${API_BASE}/reload_faces`);
        const data = await res.json();
        alert(data.message);
        updateStatus();
    } catch (err) {
        console.error("Failed to query face update index:", err);
    }
}

// Startup configurations
setInterval(updateStatus, 1500);
window.addEventListener("DOMContentLoaded", () => {
    document.getElementById("feed-img").src = `${API_BASE}/video_feed`;
    updateStatus();
});
