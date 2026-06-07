import { BrowserRouter, Link, Route, Routes } from "react-router-dom";

import { ReaderPage } from "./routes/ReaderPage";
import { ShelfPage } from "./routes/ShelfPage";

function NotFoundPage() {
  return (
    <main className="page-shell">
      <section className="state-panel">
        <p className="eyebrow">404</p>
        <h1>页面不存在</h1>
        <p>这个地址没有对应的 Read Along 页面。</p>
        <Link className="text-link" to="/">
          返回书架
        </Link>
      </section>
    </main>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<ShelfPage />} />
        <Route path="/materials/:materialId" element={<ReaderPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Routes>
    </BrowserRouter>
  );
}
