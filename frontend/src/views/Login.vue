<script setup lang="ts">

import {
    ref
} from "vue"


import {
    useRouter
} from "vue-router"


import request from "../api/request"


import {
    useUserStore
} from "../stores/user"



const username = ref("")


const password = ref("")


const router = useRouter()


const userStore = useUserStore()



async function login(){


    const formData = new URLSearchParams()


    formData.append(
        "username",
        username.value
    )


    formData.append(
        "password",
        password.value
    )



    try{


        const res = await request.post(

            "/auth/login",

            formData,

            {

                headers:{

                    "Content-Type":
                    "application/x-www-form-urlencoded"

                }

            }

        )



        userStore.setLogin(

            res.data.access_token,
            res.data.role,

            res.data.must_change_password

        )


        localStorage.setItem(
            "role",
            res.data.role
        )



        if(
            res.data.role === "ADMIN"
        ){


            router.push(
                "/admin"
            )


        }else{


            router.push(
                "/student"
            )

        }



    }catch(error){


        alert(
            "登录失败"
        )


    }


}



</script>




<template>


<main class="login-page">

<section class="login-panel">

<div class="login-mark">选</div>


<h1>
课程选课系统
</h1>

<p class="login-subtitle">学生选课与管理平台</p>


<form @submit.prevent="login">


<input

v-model="username"

placeholder="用户名"

autocomplete="username"

/>



<input

v-model="password"

type="password"

placeholder="密码"

autocomplete="current-password"

/>



<button
type="submit"
>

登录

</button>

</form>

</section>

</main>


</template>


<style scoped>

.login-page{
    min-height:100vh;
    display:grid;
    place-items:center;
    padding:24px;
    box-sizing:border-box;
    background:
        linear-gradient(135deg, rgba(17, 94, 89, 0.94), rgba(15, 23, 42, 0.98)),
        #0f172a;
}

.login-panel{
    width:min(100%, 420px);
    padding:42px 38px;
    box-sizing:border-box;
    background:#ffffff;
    border-radius:18px;
    box-shadow:0 24px 70px rgba(2, 6, 23, 0.28);
}

.login-mark{
    display:grid;
    place-items:center;
    width:48px;
    height:48px;
    margin-bottom:24px;
    border-radius:12px;
    color:#ffffff;
    background:#0f766e;
    font-weight:800;
    letter-spacing:0;
}

.login-panel h1{
    margin:0;
    color:#172033;
    font-size:30px;
    letter-spacing:0;
}

.login-subtitle{
    margin:8px 0 28px;
    color:#7a8496;
    font-size:14px;
}

.login-panel form{
    display:grid;
    gap:14px;
}

.login-panel input{
    width:100%;
    min-height:48px;
    padding:0 14px;
    box-sizing:border-box;
    border:1px solid #d7dde7;
    border-radius:9px;
    color:#172033;
    background:#f8fafc;
    font:inherit;
    outline:none;
}

.login-panel input:focus{
    border-color:#0f766e;
    box-shadow:0 0 0 3px rgba(15, 118, 110, 0.12);
}

.login-panel button{
    min-height:50px;
    margin-top:8px;
    border:0;
    border-radius:9px;
    color:#ffffff;
    background:#0f766e;
    font:600 16px inherit;
    cursor:pointer;
}

.login-panel button:hover{
    background:#115e59;
}

@media (max-width:480px){
    .login-page{
        padding:16px;
    }

    .login-panel{
        padding:32px 22px;
    }
}

</style>
