import { type RouteConfig, index, layout, route } from "@react-router/dev/routes";

export default [
  layout("layouts/shell.tsx", [
    index("routes/dashboard.tsx"),
    route("sensors", "routes/sensors.tsx"),
    route("formulas", "routes/formulas.tsx"),
    route("formulas/import", "routes/formulas-import.tsx"),
    route("batches", "routes/batches.tsx"),
    route("batches/:id", "routes/batch-detail.tsx"),
    route("simulation", "routes/simulation.tsx"),
    route("demo", "routes/demo.tsx"),
    route("about", "routes/about.tsx"),
    route("*", "routes/not-found.tsx"),
  ]),
] satisfies RouteConfig;
