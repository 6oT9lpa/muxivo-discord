import { createRouter, createWebHashHistory } from "vue-router";
import MuxivoLanding from "../views/MuxivoLanding.vue";
import GetToKnowUs from "../views/GetToKnowUs.vue";
import PanelEntry from "../views/PanelEntry.vue";
import NoAccess from "../views/NoAccess.vue";

export const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: "/", name: "muxivo-home", component: MuxivoLanding },
    { path: "/about", name: "get-to-know-us", component: GetToKnowUs },
    { path: "/panel/:module?", name: "panel", component: PanelEntry },
    { path: "/no-access", name: "no-access", component: NoAccess },
    { path: "/:pathMatch(.*)*", redirect: "/" },
  ],
});
