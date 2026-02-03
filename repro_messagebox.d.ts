import type { Message } from "@/types/Message";
import * as React from "react";
export declare const MessageBox: React.NamedExoticComponent<{
    message: Message;
    messageIndex: number;
    rewrite: (messageId: string, searchMode: string, emptyInput: () => void) => void;
    type: "list" | "single";
    isFixed?: boolean;
}>;
