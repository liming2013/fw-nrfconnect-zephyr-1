/*
 * Copyright (c) 2017 Linaro Limited
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#ifndef __INC_BOARD_H
#define __INC_BOARD_H

#if defined(CONFIG_GPIO_MMIO32)

/* USERLED0 */
#define LED0_GPIO_PORT	FPGAIO_LED0_GPIO_NAME
#define LED0_GPIO_PIN	FPGAIO_LED0_USERLED0

/* USERLED1 */
#define LED1_GPIO_PORT	FPGAIO_LED0_GPIO_NAME
#define LED1_GPIO_PIN	FPGAIO_LED0_USERLED1

/* USERPB0 */
#define SW0_GPIO_NAME	FPGAIO_BUTTON_GPIO_NAME
#define SW0_GPIO_PIN	FPGAIO_BUTTON_USERPB0

/* USERPB1 */
#define SW1_GPIO_NAME	FPGAIO_BUTTON_GPIO_NAME
#define SW1_GPIO_PIN	FPGAIO_BUTTON_USERPB1

#endif /* CONFIG_GPIO_MMIO32 */

#endif /* __INC_BOARD_H */
