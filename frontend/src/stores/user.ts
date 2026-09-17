import {
    defineStore
} from "pinia"



export const useUserStore =
defineStore("user", {


    state: () => ({


        token:
            localStorage.getItem("token") || "",


        role:
            localStorage.getItem("role") || "",

        mustChangePassword:
            localStorage.getItem("must_change_password") === "true"


    }),



    actions:{


        setLogin(
            token:string,
            role:string,
            mustChangePassword=false
        ){


            this.token = token

            this.role = role

            this.mustChangePassword = mustChangePassword


            localStorage.setItem(
                "token",
                token
            )


            localStorage.setItem(
                "role",
                role
            )

            localStorage.setItem(
                "must_change_password",
                String(mustChangePassword)
            )

        },



        logout(){


            this.token=""


            this.role=""

            this.mustChangePassword=false


            localStorage.removeItem(
                "token"
            )


            localStorage.removeItem(
                "role"
            )

            localStorage.removeItem(
                "must_change_password"
            )


        }


    }


})
