<script setup lang="ts">
import { computed, ref, watch } from "vue"
import { ElMessage } from "element-plus"

import { changePassword } from "../api/auth"

const props=defineProps<{
    modelValue:boolean
    required?:boolean
}>()

const emit=defineEmits<{
    "update:modelValue":[value:boolean]
    "password-changed":[]
}>()

const visible=computed({
    get:()=>props.modelValue,
    set:(value:boolean)=>emit("update:modelValue", value)
})
const loading=ref(false)
const form=ref({
    old_password:"",
    new_password:"",
    confirm_password:""
})

watch(
    ()=>props.modelValue,
    value=>{
        if(value){
            form.value={old_password:"", new_password:"", confirm_password:""}
        }
    }
)

async function submit(){
    if(!form.value.old_password){
        ElMessage.warning("请输入旧密码")
        return
    }
    if(form.value.new_password.length<6){
        ElMessage.warning("新密码至少需要 6 位")
        return
    }
    if(form.value.new_password!==form.value.confirm_password){
        ElMessage.warning("两次输入的新密码不一致")
        return
    }

    loading.value=true
    try{
        const response=await changePassword({
            old_password:form.value.old_password,
            new_password:form.value.new_password
        })
        if(response.data.access_token){
            localStorage.setItem("token", response.data.access_token)
        }
        localStorage.setItem("must_change_password", "false")
        ElMessage.success("密码修改成功")
        visible.value=false
        emit("password-changed")
    }catch(error:any){
        const detail=error.response?.data?.detail
        const messageMap:Record<string, string>={
            "old password is incorrect":"旧密码不正确",
            "new password must be different from the old password":"新密码不能与旧密码相同"
        }
        ElMessage.error(messageMap[detail] || (typeof detail==="string" ? detail : "密码修改失败"))
    }finally{
        loading.value=false
    }
}
</script>

<template>
<el-dialog
    v-model="visible"
    :title="required ? '首次登录请修改初始密码' : '修改密码'"
    width="460px"
    destroy-on-close
    :close-on-click-modal="!required"
    :close-on-press-escape="!required"
    :show-close="!required"
>
    <el-form label-width="100px" @submit.prevent="submit">
        <el-form-item label="旧密码" required>
            <el-input
                v-model="form.old_password"
                type="password"
                show-password
                autocomplete="current-password"
            />
        </el-form-item>
        <el-form-item label="新密码" required>
            <el-input
                v-model="form.new_password"
                type="password"
                show-password
                autocomplete="new-password"
            />
        </el-form-item>
        <el-form-item label="确认新密码" required>
            <el-input
                v-model="form.confirm_password"
                type="password"
                show-password
                autocomplete="new-password"
                @keyup.enter="submit"
            />
        </el-form-item>
    </el-form>
    <template #footer>
        <el-button v-if="!required" @click="visible=false">取消</el-button>
        <el-button type="primary" :loading="loading" @click="submit">确认修改</el-button>
    </template>
</el-dialog>
</template>
