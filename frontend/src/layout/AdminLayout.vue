<script setup lang="ts">

import {
    ref
} from "vue"

import {
    useRouter
} from "vue-router"

import ChangePasswordDialog from "../components/ChangePasswordDialog.vue"


const router=useRouter()

const passwordRequired=ref(localStorage.getItem("must_change_password")==="true")

const passwordVisible=ref(passwordRequired.value)



function logout(){


    localStorage.removeItem(
        "token"
    )


    localStorage.removeItem(
        "role"
    )

    localStorage.removeItem(
        "must_change_password"
    )


    router.push(
        "/login"
    )

}


</script>



<template>


<div class="admin-layout">


    <!-- 左侧菜单 -->

    <aside class="sidebar">


        <h2>
            选课管理系统
        </h2>



        <el-menu
            :default-active="router.currentRoute.value.path"
            router
        >


            <el-menu-item
                index="/admin"
            >

                课程管理

            </el-menu-item>



            <el-menu-item
                index="/admin/student"
            >

                学生管理

            </el-menu-item>



            <el-menu-item
                index="/admin/period"
            >

                阶段管理

            </el-menu-item>


        </el-menu>


    </aside>




    <!-- 右侧 -->

    <main class="content">


        <header class="header">


            <span>
                管理员
            </span>


            <div class="header-actions">
                <el-button @click="passwordVisible=true">修改密码</el-button>
                <el-button type="danger" @click="logout">退出登录</el-button>
            </div>


        </header>



        <router-view />

        <ChangePasswordDialog
            v-model="passwordVisible"
            :required="passwordRequired"
            @password-changed="passwordRequired=false"
        />


    </main>



</div>


</template>



<style scoped>


.admin-layout{

    display:flex;

    min-height:100vh;
    background:#f4f7f8;

}



.sidebar{

    width:240px;
    flex:0 0 240px;
    background:#102a2a;

}

.sidebar h2{
    padding:26px 24px 22px;
    margin:0;
    color:#ffffff;
    font-size:20px;
}

.sidebar :deep(.el-menu){
    border-right:0;
    background:transparent;
}

.sidebar :deep(.el-menu-item){
    height:48px;
    margin:4px 12px;
    border-radius:8px;
    color:#b9ccca;
}

.sidebar :deep(.el-menu-item:hover),
.sidebar :deep(.el-menu-item.is-active){
    color:#ffffff;
    background:#1f5b58;
}



.content{

    flex:1;

    min-width:0;
    padding:32px clamp(18px, 4vw, 52px);

}



.header{

    display:flex;

    justify-content:space-between;

    margin-bottom:28px;
    padding-bottom:18px;
    border-bottom:1px solid #dce5e5;

}

.header span{
    color:#173b3a;
    font-size:14px;
    font-weight:700;
}

.header-actions{
    display:flex;
    gap:10px;
}

@media (max-width:700px){
    .admin-layout{
        display:block;
    }

    .sidebar{
        width:100%;
    }

    .sidebar h2{
        padding:18px;
    }

    .sidebar :deep(.el-menu){
        display:flex;
        padding:0 8px 10px;
    }

    .sidebar :deep(.el-menu-item){
        flex:1;
        justify-content:center;
        margin:0 3px;
        padding:0 8px;
        font-size:13px;
    }

    .content{
        padding:22px 14px;
    }
}


</style>
