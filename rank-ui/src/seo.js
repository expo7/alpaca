const descriptions = {
  "/": ["Quantelle | Options Research and Public Paper Trade Record", "Explore Quantelle's options plans and public paper trade record, including entries, risk levels, stops, targets, and completed outcomes."],
  "/signals": ["Live Options Plans | Quantelle", "Review current and completed Quantelle paper options plans, including entries, stops, targets, and outcomes."],
  "/articles": ["Options Research Articles | Quantelle", "Read Quantelle's options research articles, market analysis, and explanations of paper trade plans."],
  "/dashboard": ["Market Dashboard | Quantelle", "Explore Quantelle's market dashboard and options research context."],
  "/support": ["Support | Quantelle", "Find help and contact information for Quantelle."],
  "/privacy": ["Privacy Policy | Quantelle", "Read Quantelle's privacy policy."],
  "/terms": ["Terms of Service | Quantelle", "Read Quantelle's terms of service."],
};

function setMeta(name, content) {
  let meta = document.querySelector(`meta[name="${name}"]`);
  if (!meta) {
    meta = document.createElement("meta");
    meta.name = name;
    document.head.append(meta);
  }
  meta.content = content;
}

export function updateSeo(path, article = null) {
  const publicPath = descriptions[path] || (path.startsWith("/articles/") ? null : descriptions["/"]);
  const title = article?.title ? `${article.title} | Quantelle` : publicPath?.[0] || "Options Research Article | Quantelle";
  const description = article?.content
    ? article.content.replace(/[#*`_\[\]()!>]/g, " ").replace(/\s+/g, " ").trim().slice(0, 155)
    : publicPath?.[1] || "Read Quantelle's options research and paper trade analysis.";
  document.title = path === "/shadow" ? "Shadow Research | Quantelle Staff" : title;
  setMeta("robots", path === "/shadow" ? "noindex, nofollow" : "index, follow");
  setMeta("description", description);
  let canonical = document.querySelector('link[rel="canonical"]');
  if (!canonical) {
    canonical = document.createElement("link");
    canonical.rel = "canonical";
    document.head.append(canonical);
  }
  canonical.href = `https://quantelle.io${path === "/" ? "/" : path.replace(/\/$/, "")}`;
}
