<template>
    <div class="flex min-h-full items-center justify-center px-4 py-6 lg:px-8 w-80 z-20"
     style="background-color: var(--bg-a);border:1px solid var(--bg-bo) ;">
        <div class="w-full max-w-md space-y-8">
            <div>
                <h2 class="mt-6 text-center text-3xl font-bold tracking-tight" style="color: var(--bg-t);">注册
                </h2>
            </div>
            <div class="-space-y-px rounded-md shadow-sm">
                <n-form ref="formRef" :model="user" :rules="rules" :show-label="false">
                    <n-form-item path="username" label="用户名">
                        <n-input v-model:value="user.username" @keydown.enter.prevent placeholder="用户名" />
                    </n-form-item>
                    <n-form-item path="password" label="密码">
                        <n-input v-model:value="user.password" type="password" @keydown.enter.prevent placeholder="密码" />
                    </n-form-item>
                    <n-form-item first path="password_agine">
                        <n-input v-model:value="password_agine" :disabled="!user.password" type="password"
                            placeholder="重复密码" @keydown.enter.prevent />
                    </n-form-item>
                    <div>
                        <n-form-item class="float-left" style="width: 68%;">
                            <n-input v-model:value="inputcode" type="text" @keydown.enter.prevent placeholder="验证码" />
                        </n-form-item>
                        <n-form-item class="float-right" style="width: 30%;">
                            <img v-if="code != undefined" :src="'data:image/png;base64,' + code?.img" alt=""
                                @click="getcode()" class=" cursor-pointer">
                            <button v-if="code == undefined" @click="getcode()" class=" text-sm "
                                type="button">获取验证码</button>
                        </n-form-item>
                    </div>

                    <n-row :gutter="[0, 24]">
                        <div class="text-sm cursor-pointer">
                            <a @click="$emit('gologin')" class="font-medium" style="color: #18a058;">登录</a>
                        </div>
                        <n-col :span="24">
                            <div class=" flex justify-between ">
                                <n-button style="color: var(--bg-t);" round type="primary" @click="$emit('closeform')">
                                    关闭
                                </n-button>
                                <n-button :disabled="user.username === '' || password_agine !== user.password" round
                                    style="color: var(--bg-t);" type="primary" @click="registerAction(user)">
                                    注册
                                </n-button>
                            </div>
                        </n-col>
                    </n-row>
                </n-form>
            </div>

        </div>
    </div>
</template>

<script async setup lang="ts">
import { reactive, ref } from 'vue'
import { OpenAPI, Service, type RegisterSuccess, UserCreate, ApiError, respCode } from '../client'
import { NButton, NForm, NFormItem, NRow, NCol, NInput, FormItemRule, FormRules } from 'naive-ui';
import { useMessage } from 'naive-ui'
const message = useMessage()
const emit = defineEmits(['gologin', 'closeform'])
defineProps<{
    showForm: boolean
}>()
const code = ref<respCode>()
const inputcode = ref('')
const user = reactive<UserCreate>({
    username: "",
    password: ""
})

const password_agine = ref('')

const rules: FormRules = {
    username: [
        {
            required: true,
            validator(rule: FormItemRule, value: string) {
                if (!value) {
                    return new Error('需要用户名')
                } else if (!/^[a-zA-Z0-9_ -]+$/.test(value)) {
                    return new Error('用户名只包含英文 _-')
                } else if (value.length <= 4) {
                    return new Error('用户名应大于4位')
                }
                return true
            },
            trigger: ['input', 'blur']
        }
    ],
    password: [
        {
            required: true,
            validator(rule: FormItemRule, value: string) {
                if (!value) {
                    return new Error('需要密码')
                } else if (value.length < 8) {
                    return new Error('密码应大于8位')
                }
                return true
            },
            trigger: ['blur', 'password-input']
        }
    ],
    password_agine: [
        {
            required: true,
            validator: (rule: FormItemRule, value: string) => {
                if (password_agine.value !== user.password) {
                    return new Error('两次密码输入不一致')
                } else {
                    return true
                }
            },
            trigger: ['input', 'blur', 'password-input']
        }
    ]
}

const registerAction = async (user: UserCreate) => {
    if (code.value === undefined) {
        message.error('请获取验证码')
        return
    }
    if (inputcode.value === '') {
        message.error('请输入验证码')
        return
    }
    await Service.register(code.value.uuid, inputcode.value, user).then((r: RegisterSuccess) => {
        message.success(r.detail)
        emit('gologin')

    }).catch((e: ApiError) => {
        message.error(e.message + e.body?.detail);
    })
}

const getcode = () => {
    Service.getCode().then((rc: respCode) => {
        code.value = rc
    }).catch((e: ApiError) => {
        message.error(e.message + e.body?.detail);
    })
}


</script>
