const { useState, useEffect } = React;

async function api(url, method = "GET", body = null) {
  let opts = { method: method, headers: { "Content-Type": "application/json" } };
  if (body) opts.body = JSON.stringify(body);
  try {
    let res = await fetch(url, opts);
    return await res.json();
  } catch (e) {
    alert("Request failed: " + e);
    return {};
  }
}

function showError(data) {
  if (data && data.error) {
    let msg = "Error: " + data.error;
    if (data.queued) msg += "\n\nThe task is saved in queue and will run when Ollama is back.";
    alert(msg);
    return true;
  }
  return false;
}

function StatusBox({ status, reload }) {
  if (!status) return <div className="box">loading status...</div>;
  const hw = status.hardware;

  async function changeModel(e) {
    await api("/api/model", "POST", { model: e.target.value });
    reload();
  }

  async function processQueue() {
    let r = await api("/api/queue/process", "POST");
    if (showError(r)) return;
    alert("Processed " + r.processed + " of " + r.total + " tasks");
    reload();
  }

  return (
    <div className="box">
      <h2>System Status</h2>
      <b>Ollama: </b>
      {status.ollama.running
        ? <span className="ok">running at {status.ollama.url}</span>
        : <span className="err">NOT running</span>}
      <br />
      <b>Model in use: </b>{status.model}<br />
      <b>Status: </b>
      {status.message == "ok" ? <span className="ok">ok</span> : <span className="err">{status.message}</span>}
      <br />
      <b>Hardware: </b>{hw.ram_gb} GB RAM, {hw.cpu_cores} cores, GPU: {hw.has_gpu ? hw.name + " (" + hw.vram_gb + " GB)" : "none"}<br />
      <b>Recommended: </b>{status.recommended.model} ({status.recommended.profile}) - {status.recommended.reason}<br />
      <b>Downloaded models: </b>{status.ollama.models.join(", ") || "-"}<br />
      <b>Queued tasks: </b>{status.pending_tasks}<br />
      {status.ollama.models.length > 0 &&
        <span>Change model:{" "}
          <select value={status.ollama.models.find(m => m.startsWith(status.model)) || ""} onChange={changeModel}>
            {status.ollama.models.map(m => <option key={m}>{m}</option>)}
          </select>
        </span>}
      <br />
      <button onClick={reload}>Refresh</button>
      <button onClick={processQueue}>Process queued tasks</button>
    </div>
  );
}

function ProductSetup({ products, productId, setProductId, reloadProducts }) {
  const [form, setForm] = useState({
    company_name: "TaskNest Software", product_name: "", description: "", price: "",
    company_info_file: "data/company_info/tasknest.txt"
  });

  function update(e) {
    setForm({ ...form, [e.target.name]: e.target.value });
  }

  async function save() {
    if (!form.product_name) {
      alert("product name is required");
      return;
    }
    let r = await api("/api/products", "POST", form);
    await reloadProducts();
    setProductId(r.id);
  }

  return (
    <div className="box">
      <h2>1. Product / Company setup</h2>
      <p>Select product:{" "}
        <select value={productId || ""} onChange={e => setProductId(e.target.value)}>
          {products.map(p => <option key={p.id} value={p.id}>{p.company_name} - {p.product_name}</option>)}
        </select>
      </p>
      <details>
        <summary>Add new product</summary>
        <input name="company_name" placeholder="Company name" value={form.company_name} onChange={update} />
        <input name="product_name" placeholder="Product name" value={form.product_name} onChange={update} />
        <textarea name="description" placeholder="Product description" value={form.description} onChange={update} />
        <input name="price" placeholder="Price" value={form.price} onChange={update} />
        <input name="company_info_file" placeholder="company info file" value={form.company_info_file} onChange={update} />
        <button onClick={save}>Save product</button>
      </details>
    </div>
  );
}

function ProfileIcp({ productId, data, reload, setLoading }) {
  async function run(what) {
    setLoading(true);
    let r = await api("/api/products/" + productId + "/" + what, "POST");
    setLoading(false);
    if (showError(r)) return;
    reload();
  }

  return (
    <div className="box">
      <h2>2. Business profile & ICP</h2>
      <button onClick={() => run("profile")}>Generate business profile</button>
      <button onClick={() => run("icp")}>Generate ICP</button>
      <div className="two-col">
        <pre>{data && data.profile ? "BUSINESS PROFILE\n" + JSON.stringify(data.profile, null, 2) : "no profile yet"}</pre>
        <pre>{data && data.icp ? "ICP\n" + JSON.stringify(data.icp, null, 2) : "no ICP yet"}</pre>
      </div>
    </div>
  );
}

function ProspectDetail({ p }) {
  if (!p) return null;
  return (
    <div>
      <h3>{p.company}</h3>
      <b>Research:</b>
      <pre>{p.research_json ? JSON.stringify(JSON.parse(p.research_json), null, 2) : "-"}</pre>
      <b>Buying signals:</b>
      <pre>{p.signals_json ? JSON.stringify(JSON.parse(p.signals_json), null, 2) : "-"}</pre>
      <b>Problem statement:</b>
      <pre>{p.problem_statement || "-"}</pre>
      <b>Score:</b> {p.score == null ? "-" : p.score} <small>{p.score_reason}</small>
      {p.emails.map(e => (
        <div className="email" key={e.id}>
          <b>Subject:</b> {e.subject}<br /><br />
          <div style={{ whiteSpace: "pre-wrap" }}>{e.body}</div>
          <small>generated by {e.source} at {e.created_at}</small>
        </div>
      ))}
    </div>
  );
}

function Prospects({ productId, setLoading, reloadAll }) {
  const [rows, setRows] = useState([]);
  const [selected, setSelected] = useState(null);

  async function load() {
    if (!productId) return;
    let r = await api("/api/products/" + productId + "/prospects");
    setRows(r);
  }

  useEffect(() => {
    load();
    setSelected(null);
  }, [productId]);

  async function view(id) {
    let p = await api("/api/prospects/" + id);
    setSelected(p);
  }

  async function step(id, name) {
    setLoading(true);
    let r = await api("/api/prospects/" + id + "/" + name, "POST");
    setLoading(false);
    if (showError(r)) { reloadAll(); return; }
    await load();
    view(id);
  }

  async function importProspects() {
    let r = await api("/api/products/" + productId + "/import_prospects", "POST");
    alert("Imported " + r.imported + " prospects");
    load();
  }

  async function runAll() {
    if (!confirm("This runs all steps for all prospects. It can take a few minutes on CPU. Continue?")) return;
    setLoading(true);
    let r = await api("/api/products/" + productId + "/run_all", "POST");
    setLoading(false);
    showError(r);
    reloadAll();
    load();
  }

  return (
    <div className="box">
      <h2>3. Prospects</h2>
      <button onClick={importProspects}>Load prospects (local data)</button>
      <button onClick={runAll}>Run full workflow for all</button>
      <table>
        <thead>
          <tr><th>Company</th><th>Contact</th><th>Industry</th><th>Signals</th><th>Score</th><th>Status</th><th>Actions</th></tr>
        </thead>
        <tbody>
          {rows.map(p => {
            let cls = "";
            if (p.score >= 60) cls = "high";
            else if (p.score != null && p.score < 40) cls = "low";
            return (
              <tr key={p.id} className={cls}>
                <td>{p.company}</td>
                <td>{p.contact_name}<br /><small>{p.contact_role}</small></td>
                <td>{p.industry}<br /><small>{p.employees} emp, {p.location}</small></td>
                <td>{p.signals.map(s => s.signal).join(", ")}</td>
                <td>{p.score == null ? "-" : p.score}</td>
                <td>{p.status}</td>
                <td>
                  <button onClick={() => step(p.id, "research")}>Research</button>
                  <button onClick={() => step(p.id, "signals")}>Signals</button>
                  <button onClick={() => step(p.id, "problem")}>Problem</button>
                  <button onClick={() => step(p.id, "score")}>Score</button>
                  <button onClick={() => step(p.id, "email")}>Email</button>
                  <button onClick={() => view(p.id)}>View</button>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      <ProspectDetail p={selected} />
    </div>
  );
}

function Replies({ setLoading, reloadAll }) {
  const [samples, setSamples] = useState([]);
  const [text, setText] = useState("");
  const [result, setResult] = useState(null);

  async function loadSamples() {
    let r = await api("/api/sample_replies");
    setSamples(r);
  }

  async function classify() {
    if (!text) return;
    setLoading(true);
    let r = await api("/api/replies/classify", "POST", { reply_text: text });
    setLoading(false);
    setResult(r);
    reloadAll();
  }

  return (
    <div className="box">
      <h2>4. Reply classification</h2>
      <button onClick={loadSamples}>Load sample replies</button>
      {samples.map((r, i) => (
        <p key={i}><button onClick={() => setText(r.text)}>use</button> <b>{r.company}:</b> {r.text}</p>
      ))}
      <textarea placeholder="paste a reply here" value={text} onChange={e => setText(e.target.value)} />
      <button onClick={classify}>Classify</button>
      {result && <pre>{JSON.stringify(result, null, 2)}</pre>}
    </div>
  );
}

function Logs() {
  const [lines, setLines] = useState([]);

  async function load() {
    let r = await api("/api/logs");
    setLines(r.lines || []);
  }

  return (
    <div className="box">
      <h2>Local model logs</h2>
      <button onClick={load}>Show logs</button>
      <pre className="logs">{lines.length ? lines.join("") : "no logs yet"}</pre>
    </div>
  );
}

function App() {
  const [status, setStatus] = useState(null);
  const [products, setProducts] = useState([]);
  const [productId, setProductId] = useState(null);
  const [productData, setProductData] = useState(null);
  const [loading, setLoading] = useState(false);

  async function loadStatus() {
    let s = await api("/api/status");
    setStatus(s);
  }

  async function loadProducts() {
    let p = await api("/api/products");
    setProducts(p);
    if (!productId && p.length > 0) setProductId(p[0].id);
  }

  async function loadProductData() {
    if (!productId) return;
    let d = await api("/api/products/" + productId);
    setProductData(d);
  }

  useEffect(() => {
    loadStatus();
    loadProducts();
  }, []);

  useEffect(() => {
    loadProductData();
  }, [productId]);

  return (
    <div>
      <h1>Local Sales Agent <small>(Harvey fork - runs on Ollama)</small></h1>
      {loading && <div id="loading">Working... (local model can take some time)</div>}
      <StatusBox status={status} reload={loadStatus} />
      <ProductSetup products={products} productId={productId} setProductId={setProductId} reloadProducts={loadProducts} />
      <ProfileIcp productId={productId} data={productData} reload={loadProductData} setLoading={setLoading} />
      <Prospects productId={productId} setLoading={setLoading} reloadAll={loadStatus} />
      <Replies setLoading={setLoading} reloadAll={loadStatus} />
      <Logs />
    </div>
  );
}

ReactDOM.createRoot(document.getElementById("root")).render(<App />);
