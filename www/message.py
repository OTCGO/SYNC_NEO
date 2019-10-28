#! /usr/bin/env python3
# coding: utf-8
# flow@SEA
# Licensed under the MIT License.

MSG = {
        "WRONG_NET":        {"code":201,"message":"wrong net"},
        "WRONG_ADDRESS":    {"code":202,"message":"wrong address"},
        "WRONG_ASSET":      {"code":203,"message":"wrong asset"},
        "WRONG_PLATFORM":   {"code":204,"message":"wrong platform"},
        "WRONG_DOMAIN":     {"code":205,"message":"wrong domain"},
        "NOT_RESOLVED":     {"code":206,"message":"domain not resolved"},
        "INSUFFICIENT_BALANCE":{"code":207,"message":"insufficient balance"},
        "WRONG_ARGUMENT":   {"code":208,"message":"wrong argument"},
        "NO_CLAIM_GAS":     {"code":209,"message":"no gas to claim"},
        "WRONG_FEE":        {"code":210,"message":"wrong fee"},
        "INSUFFICIENT_FEE": {"code":211,"message":"insufficient fee"},

        "UNKNOWN_ERROR":    {"code":500,"message":"unknown error"},


        #for nodes
        "NODE_NOT_EXIST":           {"code":600,"message":"node is not exist"},
        "NODE_ALREADY_EXIST":       {"code":601,"message":"the node already exist"},
        "NODE_CREATE_TIMEOUT":      {"code":602,"message":"node creating timeout, please finish it in 120 seconds"},
        "NODE_WAIT_PROCESS":        {"code":603,"message":"the node is existing and waiting for system to process further"},
        "REFERRER_NODE_NOT_EXIST":  {"code":604,"message":"the referrer node not exist"},

        "NODE_CREATING":            {"code":610,"message":"the node is creating, please wait"},
        "NODE_UNLOCKING":           {"code":611,"message":"the node is unlocking, please wait"},
        "NODE_WITHDRAWING":         {"code":612,"message":"the node is withdrawing, please wait"},
        "NODE_SIGNING":             {"code":613,"message":"the node is signing in, please wait"},
        "NODE_REACTIVING":          {"code":614,"message":"the node is reactiving, please wait"},

        "WRONG_ARGUMENT_MESSAGE":   {"code":620,"message":"wrong argument: message"},
        "WRONG_ARGUMENT_SIGNATURE": {"code":621,"message":"wrong argument: signature"},
        "WRONG_ARGUMENT_AMOUNT":    {"code":622,"message":"wrong argument: amount"},
        "WRONG_ARGUMENT_DAYS":      {"code":623,"message":"wrong argument: days"},
        "WRONG_ARGUMENT_REFERRER":  {"code":624,"message":"wrong argument: referrer"},
        "WRONG_ARGUMENT_TRANSACTION":  {"code":625,"message":"wrong argument: transaction"},
        "WRONG_ARGUMENT_INDEX_AND_LENGTH":  {"code":626,"message":"wrong argument: index & length"},

        "SIGNATURE_ALREADY_EXIST":  {"code":640,"message":"the signature already exist"},
        "FORBIDDEN_SIGNIN":         {"code":641,"message":"forbidden signing in"},
        "FORBIDDEN_UNLOCK":         {"code":642,"message":"forbidden signing in"},
        "ALREADY_SIGNIN":           {"code":643,"message":"already sign in today"},
        "SIGNIN_FAILURE":           {"code":644,"message":"sign in failure"},
        "UNLOCK_FAILURE":           {"code":645,"message":"unlock failure"},
        "WITHDRAW_FAILURE":         {"code":646,"message":"withdraw failure"},
        "NONE_UTXO_TO_USE":         {"code":647,"message":"there is no utxos to use"},
        "TRANSACTION_BROADCAST_FAILURE":      {"code":648,"message":"transaction broadcast failure"},
        "TOO_LESS_TO_WITHDRAW":      {"code":649,"message":"remain too less to withdraw"},
        "WAIT_LAST_WITHDRAW_FINISH": {"code":650,"message":"please wait last withdraw operation finish"},

        }
