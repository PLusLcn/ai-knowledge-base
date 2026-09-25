import { createRouter, createWebHistory } from 'vue-router'
import ChatView from '../views/ChatView.vue'

const routes = [{ path: '/', name: 'chat', component: ChatView }]

export default createRouter({
    history: createWebHistory(),
    routes,
})
